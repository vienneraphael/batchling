function isCodeLineAnchor(node) {
  return (
    node.nodeType === Node.ELEMENT_NODE &&
    node.tagName === "A" &&
    node.id.startsWith("__codelineno-")
  );
}

function highlightBashCommandTokens() {
  const codeBlocks = document.querySelectorAll(
    ".md-typeset .language-bash.highlight code, .md-typeset .language-sh.highlight code",
  );

  for (const codeBlock of codeBlocks) {
    if (codeBlock.dataset.bashTokenHighlighted === "true") {
      continue;
    }

    let atLineStart = true;
    let commandFoundInLine = false;
    const nodes = Array.from(codeBlock.childNodes);

    for (const node of nodes) {
      if (isCodeLineAnchor(node)) {
        atLineStart = true;
        commandFoundInLine = false;
        continue;
      }
      if (!atLineStart || commandFoundInLine) {
        continue;
      }

      if (node.nodeType === Node.TEXT_NODE) {
        const value = node.textContent ?? "";
        const match = value.match(/^(\s*)(\S+)([\s\S]*)$/);
        if (match === null) {
          continue;
        }

        const fragment = document.createDocumentFragment();
        if (match[1] !== "") {
          fragment.append(document.createTextNode(match[1]));
        }

        const token = document.createElement("span");
        token.className = "bash-command";
        token.textContent = match[2];
        fragment.append(token);

        if (match[3] !== "") {
          fragment.append(document.createTextNode(match[3]));
        }

        node.replaceWith(fragment);
        commandFoundInLine = true;
        atLineStart = false;
        continue;
      }

      if (
        node.nodeType === Node.ELEMENT_NODE &&
        node.classList.contains("w")
      ) {
        continue;
      }

      if (node.nodeType === Node.ELEMENT_NODE) {
        node.classList.add("bash-command");
        commandFoundInLine = true;
        atLineStart = false;
      }
    }

    codeBlock.dataset.bashTokenHighlighted = "true";
  }
}

function hasActiveSelectionInBlock(blockElement) {
  const selection = window.getSelection();
  if (selection === null || selection.isCollapsed || selection.rangeCount === 0) {
    return false;
  }

  const range = selection.getRangeAt(0);
  return blockElement.contains(range.commonAncestorContainer);
}

function isCopyDisabledForCodeBlock(codeBlock) {
  return (
    codeBlock.classList.contains("language-text") ||
    codeBlock.classList.contains("language-plaintext")
  );
}

function triggerCopyWithoutFocusScroll(copyButton) {
  copyButton.dispatchEvent(
    new MouseEvent("click", {
      bubbles: true,
      cancelable: true,
      composed: true,
      view: window,
    }),
  );
}

function installQuickCopyOnCodeBlockClick() {
  const codeBlocks = document.querySelectorAll(".md-typeset .highlight");

  for (const codeBlock of codeBlocks) {
    if (codeBlock.dataset.quickCopyBound === "true") {
      continue;
    }

    let downAt = 0;
    let downX = 0;
    let downY = 0;

    codeBlock.addEventListener("mousedown", (event) => {
      if (event.button !== 0) {
        return;
      }

      downAt = performance.now();
      downX = event.clientX;
      downY = event.clientY;
    });

    codeBlock.addEventListener("click", (event) => {
      if (event.button !== 0) {
        return;
      }

      if (isCopyDisabledForCodeBlock(codeBlock)) {
        return;
      }

      if (event.target instanceof Element && event.target.closest(".md-code__button") !== null) {
        return;
      }

      const copyButton = codeBlock.querySelector('.md-code__button[data-md-type="copy"]');
      if (copyButton === null) {
        return;
      }

      const elapsedMs = performance.now() - downAt;
      const movedPx = Math.hypot(event.clientX - downX, event.clientY - downY);

      if (elapsedMs > 260 || movedPx > 6 || hasActiveSelectionInBlock(codeBlock)) {
        return;
      }

      event.preventDefault();
      triggerCopyWithoutFocusScroll(copyButton);
    });

    codeBlock.dataset.quickCopyBound = "true";
  }
}

function isEditableTarget(target) {
  if (!(target instanceof Element)) {
    return false;
  }

  return (
    target.closest("input, textarea, select, [contenteditable], [role='textbox']") !== null
  );
}

function openSearchDialog() {
  const searchToggle = document.getElementById("__search");
  const searchQuery = document.querySelector("input[data-md-component='search-query']");
  if (!(searchToggle instanceof HTMLInputElement) || !(searchQuery instanceof HTMLInputElement)) {
    return;
  }

  if (!searchToggle.checked) {
    searchToggle.checked = true;
    searchToggle.dispatchEvent(new Event("change", { bubbles: true }));
  }

  window.requestAnimationFrame(() => {
    searchQuery.focus();
    searchQuery.select();
  });
}

function closeSearchDialog() {
  const searchToggle = document.getElementById("__search");
  const searchQuery = document.querySelector("input[data-md-component='search-query']");
  if (!(searchToggle instanceof HTMLInputElement)) {
    return;
  }

  if (searchToggle.checked) {
    searchToggle.checked = false;
    searchToggle.dispatchEvent(new Event("change", { bubbles: true }));
  }

  if (searchQuery instanceof HTMLInputElement) {
    searchQuery.blur();
  }
}

function isSearchTarget(target) {
  if (!(target instanceof Element)) {
    return false;
  }

  return target.closest(".md-search") !== null;
}

function toggleSearchDialog() {
  const searchToggle = document.getElementById("__search");
  if (!(searchToggle instanceof HTMLInputElement)) {
    return;
  }

  if (searchToggle.checked) {
    closeSearchDialog();
    return;
  }

  openSearchDialog();
}

function installSearchKeyboardShortcut() {
  if (window.__batchlingSearchShortcutBound === true) {
    return;
  }

  document.addEventListener("keydown", (event) => {
    if (!(event.ctrlKey || event.metaKey) || event.altKey) {
      return;
    }

    if (event.key.toLowerCase() !== "k") {
      return;
    }

    if (isEditableTarget(event.target) && !isSearchTarget(event.target)) {
      return;
    }

    event.preventDefault();
    toggleSearchDialog();
  });

  window.__batchlingSearchShortcutBound = true;
}

function installSearchShortcutHint() {
  const searchForm = document.querySelector(".md-search__form");
  if (!(searchForm instanceof HTMLFormElement)) {
    return;
  }

  if (searchForm.querySelector(".batchling-search-shortcut-hint") !== null) {
    return;
  }

  const hint = document.createElement("span");
  hint.className = "batchling-search-shortcut-hint";
  hint.setAttribute("aria-hidden", "true");
  hint.textContent = "Ctrl/Cmd + K";
  searchForm.append(hint);
}

function initializeCustomCodeBehaviors() {
  highlightBashCommandTokens();
  installQuickCopyOnCodeBlockClick();
  installSearchKeyboardShortcut();
  installSearchShortcutHint();
}

document.addEventListener("DOMContentLoaded", () => {
  initializeCustomCodeBehaviors();
});

if (typeof document$ !== "undefined") {
  document$.subscribe(() => {
    initializeCustomCodeBehaviors();
  });
}
