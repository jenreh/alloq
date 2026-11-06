/* Backup secrets remain in uncontrolled form inputs and short-lived HTTP bodies. */
(() => {
  if (window.alloqBackupInstalled) return;
  window.alloqBackupInstalled = true;
  let inspected = null;
  const setInput = (input, value) => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(input, value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  };
  const status = (text) => {
    const element = document.getElementById("backup-status");
    if (element) element.textContent = text;
  };
  const clearSecrets = (form) => {
    form.querySelectorAll('input[name="password"], input[name="passphrase"], input[name="passphrase_confirmation"]').forEach((input) => setInput(input, ""));
  };
  document.addEventListener("click", (event) => {
    if (event.target.closest("#backup-generate")) {
      const form = document.getElementById("backup-export");
      const bytes = crypto.getRandomValues(new Uint8Array(24));
      const phrase = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
      setInput(form.elements.passphrase, phrase);
      setInput(form.elements.passphrase_confirmation, phrase);
      status("Sicherungspassphrase erzeugt. Über das Augensymbol anzeigen und separat sicher aufbewahren.");
    }
  });
  document.addEventListener("change", (event) => {
    if (event.target.id === "backup-archive") {
      inspected = null;
      document.getElementById("backup-restore").disabled = true;
      document.getElementById("backup-metadata").textContent = "";
    }
  });
  document.addEventListener("submit", async (event) => {
    const form = event.target;
    if (!form.matches("#backup-export, #backup-import")) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    const exporting = form.id === "backup-export";
    const restoring = event.submitter?.id === "backup-restore";
    const action = exporting ? "export" : restoring ? "import" : "inspect";
    if (restoring && !inspected) return;
    const data = new FormData(form);
    if (restoring) data.set("sha256", inspected);
    clearSecrets(form);
    const buttons = [...document.querySelectorAll("#backup-export button, #backup-import button")];
    buttons.forEach((button) => { button.disabled = true; });
    status(restoring ? "Datenbank wird wiederhergestellt … Bitte warten." : "Sicherungsaktion läuft … Bitte warten.");
    try {
      const file = exporting && window.showSaveFilePicker
        ? await window.showSaveFilePicker({
          suggestedName: "alloq-backup.zip",
          types: [{ description: "Verschlüsselte ZIP-Sicherung", accept: { "application/zip": [".zip"] } }],
        }) : null;
      const response = await fetch(`${form.dataset.backupApi}/${action}`, {
        method: "POST", credentials: "include", cache: "no-store",
        headers: { "X-Alloq-Backup": "1" }, body: data,
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(typeof body.detail === "string" ? body.detail : "Die Sicherungsaktion ist fehlgeschlagen.");
      }
      if (exporting) {
        if (file && response.body) {
          await response.body.pipeTo(await file.createWritable());
        } else {
          const url = URL.createObjectURL(await response.blob());
          const link = document.createElement("a");
          link.href = url; link.download = "alloq-backup.zip"; link.click();
          setTimeout(() => URL.revokeObjectURL(url), 1000);
        }
        status("Sicherung exportiert. ZIP und Passphrase getrennt sicher aufbewahren.");
      } else {
        const body = await response.json();
        if (restoring) {
          inspected = null;
          form.reset();
          document.getElementById("backup-metadata").textContent = "";
          status(body.message);
        } else {
          inspected = body.sha256;
          document.getElementById("backup-metadata").textContent =
            `Geprüfte Sicherung vom ${body.created_at}, Version ${body.app_version}. Ziel: ${body.destination}. ` +
            "Zum Ersetzen Passwort und Sicherungspassphrase erneut eingeben.";
          status("Sicherung geprüft. Der Import ersetzt alle aktuellen Daten.");
        }
      }
    } catch (error) {
      status(error.name === "AbortError" ? "Sicherungsaktion abgebrochen." : error.message || "Die Sicherungsaktion ist fehlgeschlagen.");
    } finally {
      data.delete("password"); data.delete("passphrase"); data.delete("passphrase_confirmation");
      buttons.forEach((button) => { button.disabled = false; });
      const restore = document.getElementById("backup-restore");
      if (restore) restore.disabled = !inspected;
    }
  }, true);
  window.addEventListener("pagehide", () => {
    document.querySelectorAll("#backup-export, #backup-import").forEach(clearSecrets);
    inspected = null;
  });
})();
