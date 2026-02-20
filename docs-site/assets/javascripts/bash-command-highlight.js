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
      copyButton.click();
    });

    codeBlock.dataset.quickCopyBound = "true";
  }
}

function initializeCustomCodeBehaviors() {
  highlightBashCommandTokens();
  installQuickCopyOnCodeBlockClick();
}

document.addEventListener("DOMContentLoaded", () => {
  initializeCustomCodeBehaviors();
});

if (typeof document$ !== "undefined") {
  document$.subscribe(() => {
    initializeCustomCodeBehaviors();
  });
}
