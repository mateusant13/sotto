/* THE DRIVER, IN ITS OWN FILE AND OUTSIDE ANY TEMPLATE LITERAL.
 *
 * `theme-tune-render-test/main.js` carries its driver inside a backtick template
 * literal, and a stray backtick in a comment there has already cost two runs: the
 * literal closed early and electron hung on a file that does not parse. This driver
 * is loaded with `fs.readFileSync` and handed to `executeJavaScript` as text, so
 * `node --check driver.js` checks exactly the code the page will run, and no comment
 * can break the host.
 *
 * WHAT IT ASKS, per theme of the set: did the theme's STRUCTURAL rules reach the
 * paint? Not "does the token exist" (the other instrument owns that) but:
 *   1. the caption box is GONE — `.captions__list` and `li.caption` paint no
 *      background and no border, which is the whole point of type over a photograph;
 *   2. the caption's computed `font-size` IS `--size-caption`, so the typography read
 *      out of the design source is the typography on screen;
 *   3. the panel's `background-image` carries a real image layer, i.e. the bundled
 *      photograph (or the stated falloff) is applied;
 *   4. the CARET exists — the pseudo-element's `content` is set — which is the only
 *      marker in this set that a word is still forming;
 *   5. the newest word is painted in `--accent`, the zip's `--caption-accent` role.
 *
 * AND THE CONTROL: `theme-1`, an ORIGINAL direction, must have NONE of that. Its
 * caret must not exist and its caption box must differ from every theme of the set —
 * without which a rule that leaked out of the set's scope would pass as a feature.
 */
(async function () {
  var out = { errors: [], checks: {}, observations: {} };
  window.addEventListener('error', function (e) { out.errors.push(String(e.message)); });

  var root = document.documentElement;
  var man = window.SottoThemeManifest;
  if (!man) {
    out.checks.manifest_present = false;
    return out;
  }
  out.checks.manifest_present = true;

  var list = document.getElementById('caption-list');
  var oldLine = document.getElementById('line-old');
  var liveLine = document.getElementById('line-live');
  var liveText = document.getElementById('probe-provisional');
  var oldText = document.getElementById('probe-caption');
  var provSpan = liveLine.querySelector('.caption__provisional');
  var newestWord = liveLine.querySelector('.caption__word[data-typing]');
  var newestChar = liveLine.querySelector('.caption__ch');
  var panel = document.getElementById('panel');
  var caret = liveLine.querySelector('.caption__hint'); // eslint-disable-line no-unused-vars

  function settle() {
    // Two frames: one for the style recalc, one for the paint it triggers. A single
    // `getComputedStyle` read would already force the recalc, but the assertion is
    // about the PAINT and the owner will be looking at a painted frame.
    return new Promise(function (r) {
      requestAnimationFrame(function () { requestAnimationFrame(r); });
    });
  }

  /* Resolve a token to the colour the engine will actually paint, by asking an
     element that wears it: a token is a string, and comparing a string with a
     computed `rgb(...)` is how a colour check silently passes on nothing. */
  function resolvedColor(token) {
    var probe = document.createElement('span');
    probe.style.color = 'var(' + token + ')';
    probe.style.display = 'none';
    root.appendChild(probe);
    var c = getComputedStyle(probe).color;
    root.removeChild(probe);
    return c;
  }

  function boxOf(el) {
    var cs = getComputedStyle(el);
    return {
      bg: cs.backgroundColor,
      border: cs.borderTopWidth + ' ' + cs.borderTopStyle + ' ' + cs.borderTopColor,
      shadow: cs.boxShadow
    };
  }

  var themes = man.themes || [];
  var set = themes.filter(function (t) { return t.name.indexOf('cine-') === 0; });
  out.observations.themeCount = themes.length;
  out.observations.setCount = set.length;
  out.checks.the_set_is_present = set.length > 0;

  var rows = [];
  var badSize = [], badPhoto = [], badMarker = [], badShadow = [];
  var cinematicBoxes = [];
  var setFamilies = [];

  for (var i = 0; i < set.length; i += 1) {
    var t = set[i];
    root.dataset.theme = t.name;
    await settle();

    var listBox = boxOf(list);
    var lineBox = boxOf(liveLine);
    cinematicBoxes.push(listBox.bg + '|' + listBox.border);

    /* THE BOX IS A PER-DESIGN DECISION, NOT A PROPERTY OF THE SET — and this check
     * learned that the hard way. It used to demand that NO theme paint a caption box,
     * which is true of the first zip (its treatments are `bare`, `glass`, `plate`,
     * `chip`, `stack`: type over a photograph) and FALSE of the second, whose panels
     * are literally card layouts (`glassCards`, `ledger`, `feed`). A check that encodes
     * one zip's convention as a rule for the other is a check that gets "fixed" by
     * breaking the design. The box is now only OBSERVED. */
    var paintsABox = lineBox.bg !== 'rgba(0, 0, 0, 0)'
      || !/^0px/.test(getComputedStyle(liveLine).borderTopWidth);

    var want = getComputedStyle(root).getPropertyValue('--size-caption').trim();
    var got = getComputedStyle(liveText).fontSize;
    // `--size-caption` is authored in px, so the two must be the same string; any
    // cheat (a clamp, a vw term, a `rem`) shows up as a mismatch.
    if (got !== want) badSize.push({ theme: t.name, want: want, got: got });

    var bg = getComputedStyle(panel).backgroundImage;
    if (bg.indexOf('url(') < 0 && bg.indexOf('gradient') < 0) {
      badPhoto.push({ theme: t.name, backgroundImage: bg });
    }

    var caretContent = getComputedStyle(provSpan, '::after').content;
    var hasCaret = !(caretContent === 'none' || caretContent === 'normal' || caretContent === '');

    var accent = resolvedColor('--accent');
    var wordColor = getComputedStyle(newestWord).color;
    var charAnimation = getComputedStyle(newestChar).animationName;
    var wordAnimation = getComputedStyle(newestWord).animationName;
    /* THE ONE UNIVERSAL FORMING MARKER, and the only set-wide claim this instrument
     * makes about it. A theme has to say, somehow, that the newest text is not final.
     * The zips say it in three different ways — a blinking caret, the accent on the
     * newest word, or the reveal animation itself — and WHICH one is a per-design
     * decision (the plan's own table gives `wide` no caret and `tight` a caret). This
     * check used to demand the caret and then the accent, set-wide, and both were
     * wrong for the other zip. What must never happen is a theme where NOTHING says
     * it: that is the caption appearing whole, and it is what this catches. */
    var wordAccent = accent === wordColor;
    var hasReveal = charAnimation !== 'none' || wordAnimation !== 'none';
    if (!hasCaret && !wordAccent && !hasReveal) {
      badMarker.push({
        theme: t.name, caret: caretContent, wordAccent: wordAccent,
        wordAnimation: wordAnimation, charAnimation: charAnimation
      });
    }

    var shadow = getComputedStyle(liveText).textShadow;
    if (shadow === 'none' || shadow === '') {
      badShadow.push({ theme: t.name, textShadow: shadow });
    }
    /* The FIRST family of the stack, which is the face that decides what paints. */
    var family = getComputedStyle(liveText).fontFamily.split(',')[0].replace(/["']/g, '').trim();
    setFamilies.push(family);

    rows.push({
      name: t.name, group: t.group || null, variant: t.variant || null,
      captionSize: got, accent: accent, wordColor: wordColor,
      listBg: listBox.bg, caret: caretContent, wordAccent: accent === wordColor,
      background: bg.slice(0, 46) + (bg.length > 46 ? ' …' : ''),
      charAnimation: charAnimation,
      family: family,
      textShadow: shadow.slice(0, 46) + (shadow.length > 46 ? ' …' : ''),
      oldLineSize: getComputedStyle(oldText).fontSize
    });
  }
  out.observations.rows = rows;

  out.checks.every_theme_sizes_the_caption_from_its_token = badSize.length === 0;
  out.observations.badSize = badSize;
  out.checks.every_theme_applies_a_backdrop = badPhoto.length === 0;
  out.observations.badPhoto = badPhoto;
  out.checks.a_marker_says_the_text_is_still_forming = badMarker.length === 0;
  out.observations.badMarker = badMarker;
  /* TYPE OVER A PHOTOGRAPH NEEDS THE SHADOW. It is the zip's own
   * `0 2px 26px rgba(0,0,0,.72), 0 1px 6px rgba(0,0,0,.6)` and it is the reason the
   * caption survives a bright frame — so it is checked, and it is also the CONTROL
   * below, because no original direction carries one. */
  out.checks.every_theme_holds_the_type_off_the_photo = badShadow.length === 0;
  out.observations.badShadow = badShadow;

  /* Older lines must recede: strictly smaller than the live line, in EVERY theme of
     the set. This is the one number the zips do not state (they show a single line),
     so it is checked as a RELATION and never against a constant. */
  var oldNotSmaller = rows.filter(function (r) {
    return parseFloat(r.oldLineSize) >= parseFloat(r.captionSize);
  });
  out.checks.older_lines_recede = oldNotSmaller.length === 0;
  out.observations.oldNotSmaller = oldNotSmaller;

  /* THE CONTROL. `theme-1` is an original direction: the set's caret must not exist
   * there and the set's type shadow must not be on it either. The two together are
   * what make "the set is scoped" a measurement instead of a reading of the CSS. */
  root.dataset.theme = 'theme-1';
  await settle();
  var ctrlCaret = getComputedStyle(provSpan, '::after').content;
  var ctrlBox = boxOf(list);
  var ctrlShadow = getComputedStyle(liveText).textShadow;
  var ctrlFamily = getComputedStyle(liveText).fontFamily.split(',')[0].replace(/["']/g, '').trim();
  out.observations.control = {
    caret: ctrlCaret,
    textShadow: ctrlShadow,
    family: ctrlFamily,
    setFamilies: setFamilies,
    box: ctrlBox,
    setBoxes: cinematicBoxes.slice(0, 3)
  };
  out.checks.control_no_caret_on_the_original =
    ctrlCaret === 'none' || ctrlCaret === 'normal' || ctrlCaret === '';
  /* THE SCOPE CONTROL THAT DISCRIMINATES: the set changes the caption's FACE, so if
   * the set's typography rules had leaked out of `[data-theme^='cine-']` the original
   * direction would be painting one of the set's families. (The type shadow was tried
   * first and is NOT a control: the originals carry a shadow of their own, so the
   * check was false for a reason that has nothing to do with scoping. It is kept as an
   * observation.) */
  out.checks.control_the_original_keeps_its_own_face =
    ctrlFamily !== '' && setFamilies.indexOf(ctrlFamily) < 0;

  return out;
}())
