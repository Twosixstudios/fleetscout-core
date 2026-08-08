const { exec } = require('child_process');
const path = require('path');
const fs = require('fs');

module.exports = async () => {
    const vaultPath = app.vault.adapter.getBasePath();
    const projectDir = path.join(vaultPath, 'fleetscout-core');
    const relativeTaskPath = 'fleetscout-core/copilot/pending_task.md';
    const taskPath = path.join(projectDir, 'copilot', 'pending_task.md');
    const scriptPath = path.join(projectDir, 'copilot', 'run_build.sh');

    let promptText = "";
    try {
        promptText = await navigator.clipboard.readText();
    } catch (err) {
        console.log("Clipboard read error, defaulting to current file content.");
    }

    // 1. GO / NO-GO PROMPT
    const previewText = promptText.length > 300 
        ? promptText.substring(0, 300) + "...\n[Truncated for Preview]" 
        : promptText;

    const isApproved = confirm(
        `� GO / NO-GO: Approve OpenCode Task Execution?\n\n` +
        `----------------------------------------\n` +
        `${previewText}\n` +
        `----------------------------------------\n\n` +
        `Click 'OK' to WRITE prompt and RUN OpenCode.\n` +
        `Click 'Cancel' to abort.`
    );

    if (!isApproved) {
        new Notice("⛔ OpenCode execution aborted by user.", 4000);
        return;
    }

    // 2. LIVE-UPDATE OBSIDIAN UI & DISK
    if (promptText && promptText.trim().length > 5) {
        const file = app.vault.getAbstractFileByPath(relativeTaskPath);
        if (file) {
            await app.vault.modify(file, promptText);
        } else {
            fs.writeFileSync(taskPath, promptText, 'utf8');
        }
        new Notice("� pending_task.md updated!", 3000);
    }

    new Notice("� Running OpenCode Build...", 3000);

    // 3. EXECUTE BASH BUILD SCRIPT
    exec(`bash "${scriptPath}"`, { cwd: projectDir }, (error, stdout, stderr) => {
        if (error) {
            new Notice(`❌ Build Failed: ${error.message}`, 8000);
            return;
        }
        new Notice("✅ OpenCode Build Complete! Report updated in build_result.md", 5000);
    });
};