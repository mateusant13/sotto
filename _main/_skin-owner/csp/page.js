/* Does a FROZEN VENDOR FRAGMENT survive inside a Shadow DOM under the panel's own CSP?
   One probe, four questions: inline style attributes, an external <link> inside the shadow
   root, the vendor's @keyframes, and whether a body{} rule reaches the host. */
(function () {
  var out = {
    href: location.href,
    violations: [],
    results: {},
    errors: [],
  };
  document.addEventListener('securitypolicyviolation', function (e) {
    out.violations.push({
      directive: e.violatedDirective,
      blocked: e.blockedURI,
      sample: (e.sample || '').slice(0, 80),
    });
  });
  window.addEventListener('error', function (e) {
    out.errors.push(String(e.message || e));
  });

  function main() {
    var host = document.getElementById('skin');
    var sh = host.attachShadow ? host.attachShadow({ mode: 'open' }) : null;
    out.results.shadowRoot = !!sh;
    if (!sh) { window.__CSP_RESULT = out; return; }

    /* 1. the frozen fragment: an inline style attribute AND a custom property. */
    sh.innerHTML = ''
      + '<div id="frozen" class="frozen" style="color: rgb(255, 0, 0); --probe: 7px">'
      + '<span id="word" style="font-weight: 700">word</span></div>'
      + '<div id="animated" class="animated">anim</div>';

    /* 2. an inline <style> element, inserted from script. */
    var st = document.createElement('style');
    st.textContent = '#innermost { color: rgb(0, 255, 0); }';
    sh.appendChild(st);
    var inner = document.createElement('div');
    inner.id = 'innermost';
    inner.textContent = 'inner';
    sh.appendChild(inner);

    /* 3. the vendor stylesheet, as an external link INSIDE the shadow root. */
    var link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = '../skins-probe.css';
    sh.appendChild(link);

    function measure() {
      var frozen = sh.getElementById('frozen');
      var animated = sh.getElementById('animated');
      var cs = frozen ? getComputedStyle(frozen) : null;
      out.results.inlineStyleAttribute = cs ? cs.color : null;
      out.results.inlineCustomProperty = cs ? cs.getPropertyValue('--probe').trim() : null;
      out.results.childInlineAttribute = getComputedStyle(sh.getElementById('word')).fontWeight;
      out.results.inlineStyleElement = getComputedStyle(inner).color;
      out.results.shadowStyleSheets = sh.styleSheets.length;
      out.results.vendorRuleApplied = cs ? cs.fontSize : null;
      out.results.vendorLetterSpacing = cs ? cs.letterSpacing : null;
      var sheets = [];
      for (var i = 0; i < sh.styleSheets.length; i += 1) {
        var sheet = sh.styleSheets[i];
        var href = sheet.href || '(inline)';
        var kinds = [];
        try {
          for (var j = 0; j < sheet.cssRules.length; j += 1) {
            kinds.push(sheet.cssRules[j].type);
          }
        } catch (err) {
          kinds.push('BLOCKED:' + err.name);
        }
        sheets.push({ href: href, rules: sheet.cssRules.length, types: kinds.slice(0, 12) });
      }
      out.results.sheets = sheets;
      out.results.hostBackground = getComputedStyle(host).backgroundColor;
      out.results.bodyRuleReachedHost = out.results.hostBackground === 'rgb(40, 50, 60)';
      out.results.animationName = getComputedStyle(animated).animationName;
      out.results.dotColor = getComputedStyle(document.getElementById('skin')).color;
      window.__CSP_RESULT = out;
    }

    if (link.sheet === null) {
      link.addEventListener('load', function () { window.requestAnimationFrame(measure); });
      link.addEventListener('error', function () { out.errors.push('link-error'); measure(); });
      setTimeout(measure, 1200);
    } else {
      measure();
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', main);
  } else {
    main();
  }
})();
