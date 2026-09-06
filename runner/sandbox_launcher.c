#define _GNU_SOURCE

#include <errno.h>
#include <linux/audit.h>
#include <linux/capability.h>
#include <linux/filter.h>
#include <linux/sched.h>
#include <linux/seccomp.h>
#include <linux/securebits.h>
#include <signal.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/prctl.h>
#include <sys/resource.h>
#include <sys/syscall.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

#if defined(__x86_64__)
#define NATIVE_AUDIT_ARCH AUDIT_ARCH_X86_64
#elif defined(__aarch64__)
#define NATIVE_AUDIT_ARCH AUDIT_ARCH_AARCH64
#else
#error "sandbox launcher supports x86_64 and aarch64 only"
#endif

#define DENY_SYSCALL(number) \
    BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, (number), 0, 1), \
    BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ERRNO | EPERM)

static int fail(const char *operation) {
    fprintf(stderr, "sandbox setup failed: %s: %s\n", operation, strerror(errno));
    return 125;
}

static int drop_capabilities(void) {
    for (int capability = 0; capability <= CAP_LAST_CAP; ++capability) {
        if (prctl(PR_CAPBSET_DROP, capability, 0, 0, 0) == -1 && errno != EINVAL) {
            return -1;
        }
    }

    if (prctl(
            PR_SET_SECUREBITS,
            SECBIT_NOROOT | SECBIT_NOROOT_LOCKED |
                SECBIT_NO_SETUID_FIXUP | SECBIT_NO_SETUID_FIXUP_LOCKED,
            0,
            0,
            0) == -1) {
        return -1;
    }

    struct __user_cap_header_struct header = {
        .version = _LINUX_CAPABILITY_VERSION_3,
        .pid = 0,
    };
    struct __user_cap_data_struct data[2] = {{0}, {0}};
    if (syscall(SYS_capset, &header, data) == -1) {
        return -1;
    }
    if (prctl(PR_CAP_AMBIENT, PR_CAP_AMBIENT_CLEAR_ALL, 0, 0, 0) == -1 && errno != EINVAL) {
        return -1;
    }
    if (prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) == -1) {
        return -1;
    }
    return 0;
}

static int install_student_filter(void) {
    const unsigned int namespace_flags =
        CLONE_NEWCGROUP | CLONE_NEWIPC | CLONE_NEWNET | CLONE_NEWNS |
        CLONE_NEWPID | CLONE_NEWUSER | CLONE_NEWUTS
#ifdef CLONE_NEWTIME
        | CLONE_NEWTIME
#endif
        ;
    struct sock_filter instructions[] = {
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, arch)),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, NATIVE_AUDIT_ARCH, 1, 0),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_KILL_PROCESS),
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, nr)),
        DENY_SYSCALL(__NR_chroot),
        DENY_SYSCALL(__NR_unshare),
        DENY_SYSCALL(__NR_setns),
        DENY_SYSCALL(__NR_mount),
        DENY_SYSCALL(__NR_umount2),
        DENY_SYSCALL(__NR_pivot_root),
#ifdef __NR_open_tree
        DENY_SYSCALL(__NR_open_tree),
#endif
#ifdef __NR_move_mount
        DENY_SYSCALL(__NR_move_mount),
#endif
#ifdef __NR_fsopen
        DENY_SYSCALL(__NR_fsopen),
#endif
#ifdef __NR_fsmount
        DENY_SYSCALL(__NR_fsmount),
#endif
#ifdef __NR_mount_setattr
        DENY_SYSCALL(__NR_mount_setattr),
#endif
#ifdef __NR_clone3
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_clone3, 0, 1),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ERRNO | ENOSYS),
#endif
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, __NR_clone, 0, 4),
        BPF_STMT(BPF_LD | BPF_W | BPF_ABS, offsetof(struct seccomp_data, args[0])),
        BPF_STMT(BPF_ALU | BPF_AND | BPF_K, namespace_flags),
        BPF_JUMP(BPF_JMP | BPF_JEQ | BPF_K, 0, 1, 0),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ERRNO | EPERM),
        BPF_STMT(BPF_RET | BPF_K, SECCOMP_RET_ALLOW),
    };
    struct sock_fprog program = {
        .len = (unsigned short)(sizeof(instructions) / sizeof(instructions[0])),
        .filter = instructions,
    };
    return prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, &program);
}

int main(int argc, char **argv) {
    if (argc != 4) {
        fputs("sandbox setup failed: invalid arguments\n", stderr);
        return 125;
    }

    char *end = NULL;
    errno = 0;
    long process_limit = strtol(argv[3], &end, 10);
    if (errno != 0 || end == argv[3] || *end != '\0' || process_limit < 1 || process_limit > 4096) {
        fputs("sandbox setup failed: invalid process limit\n", stderr);
        return 125;
    }

    if (chdir(argv[1]) == -1) {
        return fail("chdir");
    }
    if (chroot(".") == -1) {
        return fail("chroot");
    }
    if (chdir("/") == -1) {
        return fail("chdir root");
    }
    if (drop_capabilities() == -1) {
        return fail("drop capabilities");
    }
    if (install_student_filter() == -1) {
        return fail("install seccomp filter");
    }

    pid_t child = fork();
    if (child == -1) {
        return fail("fork");
    }
    if (child == 0) {
        struct rlimit limit = {
            .rlim_cur = (rlim_t)process_limit,
            .rlim_max = (rlim_t)process_limit,
        };
        if (setrlimit(RLIMIT_NPROC, &limit) == -1) {
            _exit(125);
        }
        execl(argv[2], argv[2], (char *)NULL);
        _exit(126);
    }

    int status = 0;
    while (waitpid(child, &status, 0) == -1) {
        if (errno != EINTR) {
            return fail("waitpid");
        }
    }
    if (WIFEXITED(status)) {
        return WEXITSTATUS(status);
    }
    if (WIFSIGNALED(status)) {
        return 128 + WTERMSIG(status);
    }
    return 125;
}
