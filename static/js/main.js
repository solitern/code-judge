document.addEventListener("DOMContentLoaded", function () {
  // ===== 配置 =====
  var WANDBOX_API = "https://wandbox.org/api/compile.json";
  var PROBLEMS_FILE = "problems/week10.json";

  // ===== 状态 =====
  var problems = [];
  var testCases = {};
  var currentProblemIdx = 0;
  var editor = null;
  var savedCodes = {};
  var hasLoaded = false;

  // ===== DOM =====
  var $tabs = document.getElementById("problemTabs");
  var $pageTitle = document.getElementById("pageTitle");
  var $title = document.getElementById("problemTitle");
  var $content = document.getElementById("problemContent");
  var $btnRun = document.getElementById("btnRun");
  var $btnSubmit = document.getElementById("btnSubmit");
  var $btnReset = document.getElementById("btnReset");
  var $resultPanel = document.getElementById("resultPanel");
  var $resultTitle = document.getElementById("resultTitle");
  var $resultBody = document.getElementById("resultBody");
  var $btnClose = document.getElementById("btnCloseResult");
  var $status = document.getElementById("statusText");

  // ===== 初始化编辑器 =====
  editor = CodeMirror.fromTextArea(document.getElementById("codeEditor"), {
    mode: "text/x-csrc",
    theme: "dracula",
    lineNumbers: true,
    matchBrackets: true,
    autoCloseBrackets: true,
    tabSize: 4,
    indentUnit: 4,
    indentWithTabs: false,
    lineWrapping: false,
  });

  // ===== 加载题目 =====
  fetch(PROBLEMS_FILE)
    .then(function (r) { return r.json(); })
    .then(function (data) {
      document.title = data.title;
      $pageTitle.textContent = data.title;
      data.problems.forEach(function (p) {
        testCases[p.id] = p.testCases;
      });
      problems = data.problems;
      renderTabs();
      switchProblem(0);
    })
    .catch(function () {
      $content.innerHTML =
        '<div class="loading" style="color:var(--red)">加载失败，请刷新重试</div>';
    });

  // ===== 渲染选项卡 =====
  function renderTabs() {
    $tabs.innerHTML = "";
    problems.forEach(function (p, i) {
      var btn = document.createElement("button");
      btn.className = "tab-btn" + (i === 0 ? " active" : "");
      btn.textContent = "\u9898\u76EE " + p.id + "\uFF1A" + p.title;
      btn.onclick = function () { switchProblem(i); };
      $tabs.appendChild(btn);
    });
  }

  // ===== 切换题目 =====
  function switchProblem(idx) {
    if (hasLoaded) {
      savedCodes[currentProblemIdx] = editor.getValue();
    }
    currentProblemIdx = idx;
    var p = problems[idx];

    document.querySelectorAll(".tab-btn").forEach(function (btn, i) {
      btn.classList.toggle("active", i === idx);
    });

    $title.textContent = "\u9898\u76EE " + p.id + "\uFF1A" + p.title;
    renderProblem(p);

    var code = savedCodes[idx] !== undefined ? savedCodes[idx] : p.template;
    editor.setValue(code);
    editor.refresh();
    hasLoaded = true;

    hideResult();
    $status.textContent = "";
  }

  // ===== 渲染题目描述 =====
  function renderProblem(p) {
    var html = "";
    html += section("\u9898\u76EE\u63CF\u8FF0", '<div class="problem-text">' + esc(p.description) + "</div>");
    html += section("\u8F93\u5165\u683C\u5F0F", '<div class="problem-text">' + esc(p.inputFormat) + "</div>");
    html += section("\u8F93\u51FA\u683C\u5F0F", '<div class="problem-text">' + esc(p.outputFormat) + "</div>");

    var samplesHtml = "";
    p.samples.forEach(function (s, i) {
      var label = p.samples.length > 1 ? " " + (i + 1) : "";
      samplesHtml += '<div class="sample-group">';
      samplesHtml += '<div class="sample-label">\u8F93\u5165\u6837\u4F8B' + label + "</div>";
      samplesHtml += '<div class="code-block">' + esc(s.input) + "</div>";
      samplesHtml += '<div class="sample-label" style="margin-top:8px">\u8F93\u51FA\u6837\u4F8B' + label + "</div>";
      samplesHtml += '<div class="code-block">' + esc(s.output) + "</div>";
      if (s.explanation) {
        samplesHtml += '<div class="explanation"><pre>' + esc(s.explanation) + "</pre></div>";
      }
      samplesHtml += "</div>";
    });
    html += section("\u6837\u4F8B", samplesHtml);

    if (p.hint) {
      html += section("\u63D0\u793A", '<div class="hint-box">' + esc(p.hint) + "</div>");
    }

    $content.innerHTML = html;
  }

  function section(title, body) {
    return '<div class="problem-section"><div class="section-title">' + esc(title) + "</div>" + body + "</div>";
  }

  function esc(s) {
    var d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

  // ===== Wandbox API 调用 =====
  function executeCode(code, stdin) {
    return fetch(WANDBOX_API, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        code: code,
        compiler: "gcc-head",
        stdin: stdin,
        save: false,
      }),
    }).then(function (r) {
      if (!r.ok) throw new Error("API \u8BF7\u6C42\u5931\u8D25 (" + r.status + ")");
      return r.json();
    });
  }

  function parseResult(data) {
    // 编译错误：status 非 "0" 且无 program_output
    if (data.compiler_error && data.status !== "0" && !data.program_output) {
      return { status: "compile_error", message: data.compiler_error || data.compiler_message };
    }
    // 信号终止（超时等）
    if (data.signal) {
      return { status: "timeout", message: "\u8FD0\u884C\u8D85\u65F6\u6216\u88AB\u4FE1\u53F7\u7EC8\u6B62 (" + data.signal + ")" };
    }
    // 运行时错误
    if (data.status !== "0") {
      return { status: "runtime_error", message: data.program_error || "\u8FD0\u884C\u65F6\u9519\u8BEF", output: data.program_output };
    }
    // 成功
    return { status: "success", output: data.program_output };
  }

  // ===== 运行 =====
  $btnRun.addEventListener("click", function () {
    var p = problems[currentProblemIdx];
    var code = editor.getValue();
    var input = p.samples[0].input;

    setLoading(true, "\u7F16\u8BD1\u8FD0\u884C\u4E2D...");
    hideResult();

    executeCode(code, input)
      .then(function (data) {
        setLoading(false);
        var r = parseResult(data);
        showRunResult(r, p.samples[0]);
      })
      .catch(function (err) {
        setLoading(false);
        showError("\u7F51\u7EDC\u9519\u8BEF\uFF1A" + err.message);
      });
  });

  // ===== 提交 =====
  $btnSubmit.addEventListener("click", function () {
    var p = problems[currentProblemIdx];
    var code = editor.getValue();
    var cases = testCases[p.id];

    if (!cases || cases.length === 0) {
      showError("\u6CA1\u6709\u6D4B\u8BD5\u7528\u4F8B");
      return;
    }

    setLoading(true, "\u7F16\u8BD1\u5E76\u8BC4\u6D4B\u4E2D...");
    hideResult();

    var results = [];
    var chain = Promise.resolve();

    cases.forEach(function (tc, i) {
      chain = chain.then(function () {
        return executeCode(code, tc.input).then(function (data) {
          var r = parseResult(data);

          if (r.status === "compile_error") {
            results.push({ id: i + 1, passed: false, input: tc.input, expected: tc.output.trim(), actual: "\u7F16\u8BD1\u9519\u8BEF" });
            return;
          }

          var actual = (r.output || "").trimEnd();
          var expected = tc.output.trim();
          results.push({
            id: i + 1,
            passed: r.status === "success" && actual === expected,
            input: tc.input,
            expected: expected,
            actual: r.status === "success" ? actual : (r.message || "\u8FD0\u884C\u5931\u8D25"),
          });
        });
      });
    });

    chain
      .then(function () {
        setLoading(false);
        // 如果第一个就是编译错误，直接显示编译错误
        if (results.length > 0 && results[0].actual === "\u7F16\u8BD1\u9519\u8BEF") {
          // 重新执行一次拿编译错误信息
          return executeCode(code, "").then(function (data) {
            var r = parseResult(data);
            showCompileError(r.message);
          });
        }
        showSubmitResult(results);
      })
      .catch(function (err) {
        setLoading(false);
        showError("\u7F51\u7EDC\u9519\u8BEF\uFF1A" + err.message);
      });
  });

  // ===== 重置 =====
  $btnReset.addEventListener("click", function () {
    if (confirm("\u786E\u5B9A\u8981\u91CD\u7F6E\u4EE3\u7801\u4E3A\u521D\u59CB\u6A21\u677F\u5417\uFF1F")) {
      var p = problems[currentProblemIdx];
      editor.setValue(p.template);
      savedCodes[currentProblemIdx] = p.template;
      hideResult();
    }
  });

  // ===== 关闭结果 =====
  $btnClose.addEventListener("click", hideResult);

  // ===== 显示运行结果 =====
  function showRunResult(r, sample) {
    $resultPanel.style.display = "block";
    if (r.status === "success") {
      var actual = r.output.trimEnd();
      var expected = sample.output.trim();
      var match = actual === expected;
      $resultTitle.textContent = "\u8FD0\u884C\u7ED3\u679C";
      $resultBody.innerHTML =
        '<div class="submit-summary ' + (match ? "all-pass" : "has-fail") + '">' +
        (match ? "&#x2705; \u8F93\u51FA\u4E0E\u6837\u4F8B\u4E00\u81F4" : "&#x274C; \u8F93\u51FA\u4E0E\u6837\u4F8B\u4E0D\u4E00\u81F4") +
        "</div>" +
        '<div class="test-case-item"><div class="tc-detail">' +
        tcRow("\u8F93\u5165\uFF1A", sample.input) +
        tcRow("\u671F\u671B\uFF1A", expected) +
        tcRow("\u5B9E\u9645\uFF1A", actual) +
        "</div></div>";
    } else {
      showError(formatError(r));
    }
  }

  // ===== 显示提交结果 =====
  function showSubmitResult(results) {
    $resultPanel.style.display = "block";
    var allPass = results.every(function (r) { return r.passed; });
    var passCount = results.filter(function (r) { return r.passed; }).length;

    $resultTitle.textContent = "\u8BC4\u6D4B\u7ED3\u679C\uFF08" + passCount + "/" + results.length + " \u901A\u8FC7\uFF09";

    var html =
      '<div class="submit-summary ' + (allPass ? "all-pass" : "has-fail") + '">' +
      (allPass ? "&#x2705; \u6240\u6709\u6D4B\u8BD5\u7528\u4F8B\u901A\u8FC7\uFF01" : "&#x274C; \u90E8\u5206\u6D4B\u8BD5\u7528\u4F8B\u672A\u901A\u8FC7") +
      "</div>";

    results.forEach(function (r) {
      html += '<div class="test-case-item">';
      html += '<span class="tc-badge ' + (r.passed ? "pass" : "fail") + '">' + (r.passed ? "PASS" : "FAIL") + "</span>";
      html += '<div class="tc-detail">';
      html += tcRow("\u8F93\u5165\uFF1A", r.input);
      html += tcRow("\u671F\u671B\uFF1A", r.expected);
      html += tcRow("\u5B9E\u9645\uFF1A", r.actual);
      html += "</div></div>";
    });

    $resultBody.innerHTML = html;
  }

  function showCompileError(message) {
    $resultPanel.style.display = "block";
    $resultTitle.textContent = "\u7F16\u8BD1\u9519\u8BEF";
    $resultBody.innerHTML = '<div class="error-message">' + esc(message) + "</div>";
  }

  // ===== 辅助函数 =====
  function tcRow(label, value) {
    return '<div class="tc-row"><span class="tc-label">' + label + '</span><span class="tc-value">' + esc(value) + "</span></div>";
  }

  function showError(msg) {
    $resultPanel.style.display = "block";
    $resultTitle.textContent = "\u9519\u8BEF";
    $resultBody.innerHTML = '<div class="error-message">' + esc(msg) + "</div>";
  }

  function formatError(r) {
    if (r.status === "compile_error") return "\u7F16\u8BD1\u9519\u8BEF\uFF1A\n" + r.message;
    if (r.status === "runtime_error") return "\u8FD0\u884C\u65F6\u9519\u8BEF\uFF1A\n" + r.message;
    if (r.status === "timeout") return r.message;
    return r.message || "\u672A\u77E5\u9519\u8BEF";
  }

  function hideResult() {
    $resultPanel.style.display = "none";
    $resultBody.innerHTML = "";
  }

  function setLoading(loading, text) {
    $btnRun.disabled = loading;
    $btnSubmit.disabled = loading;
    $status.innerHTML = loading
      ? '<span class="spinner" style="border-color:var(--gray-300);border-top-color:var(--primary)"></span>' + esc(text || "")
      : "";
  }
});
