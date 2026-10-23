import DefaultTheme from "vitepress/theme";
import "./image-zoom.css";

const DIALOG_ID = "docs-image-zoom";

function openImageZoom(image: HTMLImageElement): void {
  let dialog = document.getElementById(DIALOG_ID) as HTMLDialogElement | null;

  if (!dialog) {
    dialog = document.createElement("dialog");
    dialog.id = DIALOG_ID;
    dialog.setAttribute("aria-label", "Image preview");
    dialog.addEventListener("click", () => dialog?.close());
    document.body.append(dialog);
  }

  dialog.replaceChildren();

  const enlargedImage = document.createElement("img");
  enlargedImage.src = image.currentSrc || image.src;
  enlargedImage.alt = image.alt;
  dialog.append(enlargedImage);
  dialog.showModal();
}

if (typeof window !== "undefined") {
  document.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLImageElement)) return;
    if (!target.closest(".vp-doc")) return;

    event.preventDefault();
    openImageZoom(target);
  });
}

export default {
  ...DefaultTheme,
};
