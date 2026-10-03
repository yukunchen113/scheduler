const vscode = require('vscode');
const cp = require('child_process');
const fs = require('fs');
const path = require('path');

let outputChannel;

function getPythonPath() {
    const config = vscode.workspace.getConfiguration('plex');
    const customPath = config.get('pythonPath');
    if (customPath && customPath.trim() !== '' && fs.existsSync(customPath)) {
        return customPath;
    }
    if (process.env.VIRTUAL_ENV) {
        const venvPy = path.join(process.env.VIRTUAL_ENV, 'bin', 'python');
        if (fs.existsSync(venvPy)) {
            return venvPy;
        }
    }
    if (process.env.CONDA_PREFIX) {
        const condaPy = path.join(process.env.CONDA_PREFIX, 'bin', 'python');
        if (fs.existsSync(condaPy)) {
            return condaPy;
        }
    }
    return 'python3';
}

function getWorkspaceRoot(documentUri) {
    if (documentUri) {
        const folder = vscode.workspace.getWorkspaceFolder(documentUri);
        if (folder) {
            return folder.uri.fsPath;
        }
        let dir = path.dirname(documentUri.fsPath);
        while (dir && dir !== path.dirname(dir)) {
            if (fs.existsSync(path.join(dir, 'setup.py')) || fs.existsSync(path.join(dir, 'routines')) || fs.existsSync(path.join(dir, 'weekly'))) {
                return dir;
            }
            dir = path.dirname(dir);
        }
    }
    if (vscode.workspace.workspaceFolders && vscode.workspace.workspaceFolders.length > 0) {
        return vscode.workspace.workspaceFolders[0].uri.fsPath;
    }
    return process.cwd();
}

function runPlexCommand(args, cwd) {
    return new Promise((resolve, reject) => {
        const python = getPythonPath();
        const root = cwd || getWorkspaceRoot();
        outputChannel.appendLine(`[Plex] Running: ${python} ${args.join(' ')} (in ${root})`);

        const env = Object.assign({}, process.env, {
            PYTHONPATH: root + (process.env.PYTHONPATH ? path.delimiter + process.env.PYTHONPATH : '')
        });

        cp.execFile(python, args, { cwd: root, env: env }, (error, stdout, stderr) => {
            if (stdout) {
                outputChannel.appendLine(stdout);
            }
            if (stderr) {
                outputChannel.appendLine(`[Error] ${stderr}`);
            }
            if (error) {
                reject({ error, stdout, stderr });
            } else {
                resolve({ stdout, stderr });
            }
        });
    });
}

function getRoutinesList() {
    const root = getWorkspaceRoot();
    const routinesDir = path.join(root, 'routines');
    if (!fs.existsSync(routinesDir)) {
        return [];
    }
    const files = fs.readdirSync(routinesDir);
    return files
        .filter(f => f.endsWith('.txt') || f.endsWith('.py'))
        .map(f => {
            const name = f.replace(/\.(txt|py)$/, '');
            const ext = path.extname(f);
            return {
                label: `$(symbol-event) ${name}`,
                description: ext === '.py' ? 'Python generator script' : 'Routine text template',
                routineName: name,
                filename: f,
                fullPath: path.join(routinesDir, f)
            };
        });
}

class PlexCodeLensProvider {
    constructor() {
        this._onDidChangeCodeLenses = new vscode.EventEmitter();
        this.onDidChangeCodeLenses = this._onDidChangeCodeLenses.event;
    }

    refresh() {
        this._onDidChangeCodeLenses.fire();
    }

    provideCodeLenses(document, token) {
        const filePath = document.uri.fsPath;
        const fileName = path.basename(filePath);
        const lenses = [];

        // Weekly files (e.g. weekly/2026-W41.txt or files starting with WEEK header)
        if (filePath.includes('/weekly/') || fileName.match(/^\d{4}-W\d{2}\.txt$/)) {
            return this.provideWeeklyCodeLenses(document);
        }

        // Daily files (e.g. daily/2026-10-05.ans)
        if (filePath.includes('/daily/') || fileName.match(/^\d{4}-\d{2}-\d{2}\.(ans|txt)$/)) {
            return this.provideDailyCodeLenses(document);
        }

        return lenses;
    }

    provideWeeklyCodeLenses(document) {
        const lenses = [];
        const lines = document.getText().split('\n');

        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];

            // 1. Week Header banner: WEEK XX (YYYY-MM-DD to YYYY-MM-DD)
            const weekMatch = line.match(/^WEEK\s+(\d+)\s*\(([\d-]+)\s+to\s+([\d-]+)\)/i);
            if (weekMatch) {
                const range = new vscode.Range(i, 0, i, line.length);
                lenses.push(
                    new vscode.CodeLens(range, {
                        title: "$(sync) Recalculate Week",
                        command: "plex.evaluateWeek",
                        tooltip: "Re-evaluate hours and status for all 7 days"
                    }),
                    new vscode.CodeLens(range, {
                        title: "$(export) Export to Daily Files",
                        command: "plex.exportDaily",
                        tooltip: "Export all 7 days into daily/*.ans execution files"
                    }),
                    new vscode.CodeLens(range, {
                        title: "$(sparkle) Re-Init with Routine...",
                        command: "plex.initWeek",
                        tooltip: "Re-initialize this weekly plan with a routine generator"
                    })
                );
            }

            // 2. Day Header: === Monday (2026-10-05) ===
            const dayMatch = line.match(/^===+\s*([A-Za-z]+)\s*(?:\(([\d-]+)\))?\s*===+/);
            if (dayMatch) {
                const dayName = dayMatch[1];
                const dateStr = dayMatch[2];
                const range = new vscode.Range(i, 0, i, line.length);

                // Check next line for status comment
                let statusBadge = "$(calendar) " + dayName;
                if (i + 1 < lines.length) {
                    const nextLine = lines[i + 1];
                    const statusMatch = nextLine.match(/^#\s*\[(.*)\]/);
                    if (statusMatch) {
                        statusBadge = `📊 ${statusMatch[1]}`;
                    }
                }

                lenses.push(
                    new vscode.CodeLens(range, {
                        title: statusBadge,
                        command: "plex.showDayInfo",
                        arguments: [dayName, dateStr],
                        tooltip: `Day status for ${dayName} (${dateStr})`
                    })
                );

                if (dateStr) {
                    lenses.push(
                        new vscode.CodeLens(range, {
                            title: "$(export) Export Day",
                            command: "plex.exportSingleDay",
                            arguments: [dateStr],
                            tooltip: `Export ${dayName} (${dateStr}) to daily/${dateStr}.ans`
                        })
                    );
                }

                lenses.push(
                    new vscode.CodeLens(range, {
                        title: "$(add) Insert Routine...",
                        command: "plex.insertRoutine",
                        arguments: [i + 2],
                        tooltip: `Insert routine template tasks into ${dayName}`
                    })
                );
            }
        }

        return lenses;
    }

    provideDailyCodeLenses(document) {
        const lenses = [];
        const lines = document.getText().split('\n');

        let splitterIndex = -1;
        for (let i = 0; i < lines.length; i++) {
            if (lines[i].startsWith('-------------')) {
                splitterIndex = i;
                break;
            }
        }

        const targetLine = splitterIndex >= 0 ? splitterIndex : 0;
        const lineContent = lines[targetLine] || "";
        const range = new vscode.Range(targetLine, 0, targetLine, lineContent.length);

        lenses.push(
            new vscode.CodeLens(range, {
                title: "$(location) Plan Commutes",
                command: "plex.planCommute",
                tooltip: "Interactive commute & route planner for daily schedule"
            }),
            new vscode.CodeLens(range, {
                title: "$(play) Run Plex Engine",
                command: "plex.runDaily",
                tooltip: "Calculate timings and update schedule"
            }),
            new vscode.CodeLens(range, {
                title: "$(cloud-upload) Push to Google Calendar",
                command: "plex.pushCalendar",
                tooltip: "Push schedule to Google Calendar & Notion"
            })
        );

        return lenses;
    }
}

function activate(context) {
    outputChannel = vscode.window.createOutputChannel('Plex');
    context.subscriptions.push(outputChannel);

    const codeLensProvider = new PlexCodeLensProvider();
    const selector = [
        { scheme: 'file', pattern: '**/*.{txt,ans}' }
    ];

    context.subscriptions.push(
        vscode.languages.registerCodeLensProvider(selector, codeLensProvider)
    );

    // Status bar item
    const statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    context.subscriptions.push(statusBarItem);

    function updateStatusBar(document) {
        if (!document) {
            statusBarItem.hide();
            return;
        }
        const filePath = document.uri.fsPath;
        if (filePath.includes('/weekly/') || path.basename(filePath).match(/^\d{4}-W\d{2}\.txt$/)) {
            const text = document.getText();
            const totalMatch = text.match(/Week Total:\s*([^\n\r]+)/i);
            const weekMatch = text.match(/WEEK\s+(\d+)/i);
            const weekNum = weekMatch ? `W${weekMatch[1]}` : 'Week';
            const totalInfo = totalMatch ? totalMatch[1].replace(/Status:\s*/, '') : 'Ready';

            statusBarItem.text = `$(calendar) ${weekNum}: ${totalInfo}`;
            statusBarItem.tooltip = "Click to export weekly plan to daily files";
            statusBarItem.command = "plex.exportDaily";
            statusBarItem.show();
        } else if (filePath.includes('/daily/') || path.basename(filePath).match(/^\d{4}-\d{2}-\d{2}\.(ans|txt)$/)) {
            statusBarItem.text = `$(play) Plex: Run Daily`;
            statusBarItem.tooltip = "Click to run Plex schedule engine";
            statusBarItem.command = "plex.runDaily";
            statusBarItem.show();
        } else {
            statusBarItem.hide();
        }
    }

    vscode.window.onDidChangeActiveTextEditor(editor => {
        updateStatusBar(editor ? editor.document : null);
    });

    if (vscode.window.activeTextEditor) {
        updateStatusBar(vscode.window.activeTextEditor.document);
    }

    // Auto-eval on save
    let isEvaluating = false;
    context.subscriptions.push(
        vscode.workspace.onDidSaveTextDocument(async document => {
            if (isEvaluating) {
                return;
            }
            const filePath = document.uri.fsPath;
            const config = vscode.workspace.getConfiguration('plex');
            if (config.get('autoEvalOnSave', true)) {
                if (filePath.includes('/weekly/') || path.basename(filePath).match(/^\d{4}-W\d{2}\.txt$/)) {
                    isEvaluating = true;
                    try {
                        await runPlexCommand(['-m', 'plex.weekly', '--eval', '--file', filePath]);
                        codeLensProvider.refresh();
                        updateStatusBar(document);
                    } catch (err) {
                        vscode.window.showErrorMessage(`Plex Evaluation Failed: ${err.stderr || err.error?.message}`);
                    } finally {
                        isEvaluating = false;
                    }
                }
            }
        })
    );

    // Command: plex.setup
    context.subscriptions.push(
        vscode.commands.registerCommand('plex.setup', async () => {
            const terminal = vscode.window.createTerminal("Plex Setup");
            terminal.show();
            terminal.sendText(`${getPythonPath()} -m plex.setup`);
        })
    );

    // Command: plex.generateWeek
    context.subscriptions.push(
        vscode.commands.registerCommand('plex.generateWeek', async () => {
            const weekPicks = [
                { label: "$(calendar) This Week", description: "Current week", value: "current" },
                { label: "$(arrow-right) Next Week", description: "Upcoming week", value: "next" },
                { label: "$(edit) Custom Date...", description: "Specify a date (YYYY-MM-DD)", value: "custom" }
            ];

            const pickedWeek = await vscode.window.showQuickPick(weekPicks, {
                placeHolder: "Select which week to plan"
            });
            if (!pickedWeek) return;

            let targetDateStr = null;
            if (pickedWeek.value === "current") {
                targetDateStr = new Date().toISOString().slice(0, 10);
            } else if (pickedWeek.value === "next") {
                const nextWeek = new Date();
                nextWeek.setDate(nextWeek.getDate() + 7);
                targetDateStr = nextWeek.toISOString().slice(0, 10);
            } else if (pickedWeek.value === "custom") {
                targetDateStr = await vscode.window.showInputBox({
                    prompt: "Enter a date inside the target week (YYYY-MM-DD)",
                    value: new Date().toISOString().slice(0, 10)
                });
                if (!targetDateStr) return;
            }

            const routines = getRoutinesList();
            const routinePicks = [
                { label: "$(symbol-structure) Blank Week", description: "Clean weekly template with no extra routines", routineName: null, isBlank: true }
            ];
            routines.forEach(r => routinePicks.push(r));
            routinePicks.push({
                label: "$(edit) Custom Routine/Generator...",
                description: "Type routine name or script path",
                routineName: null,
                isCustom: true
            });

            const pickedRoutine = await vscode.window.showQuickPick(routinePicks, {
                placeHolder: "Select a routine template generator to pre-populate"
            });
            if (!pickedRoutine) return;

            let chosenRoutine = pickedRoutine.routineName;
            if (pickedRoutine.isCustom) {
                chosenRoutine = await vscode.window.showInputBox({
                    prompt: "Enter routine template name or script path (e.g. school, routines/my_gen.py)",
                    value: "school"
                });
                if (!chosenRoutine) return;
            }

            const args = ['-m', 'plex.weekly', '--init'];
            if (chosenRoutine) {
                args.push(chosenRoutine);
            }
            if (targetDateStr) {
                args.push('--date', targetDateStr);
            }
            args.push('--overwrite');

            await vscode.window.withProgress({
                location: vscode.ProgressLocation.Notification,
                title: "Plex: Generating Weekly Plan...",
                cancellable: false
            }, async () => {
                try {
                    const res = await runPlexCommand(args);
                    const match = res.stdout.match(/weekly\/[\w-]+\.txt/);
                    let targetPath = null;
                    if (match) {
                        targetPath = path.join(getWorkspaceRoot(), match[0]);
                    }
                    if (targetPath && fs.existsSync(targetPath)) {
                        const doc = await vscode.workspace.openTextDocument(targetPath);
                        await vscode.window.showTextDocument(doc);
                    }
                    vscode.window.showInformationMessage(`Plex: Weekly plan generated successfully!`);
                } catch (err) {
                    vscode.window.showErrorMessage(`Plex Generate Week Failed: ${err.stderr || err.error?.message}`);
                }
            });
        })
    );

    // Command: plex.evaluateWeek
    context.subscriptions.push(
        vscode.commands.registerCommand('plex.evaluateWeek', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) return;
            const filePath = editor.document.uri.fsPath;

            await vscode.window.withProgress({
                location: vscode.ProgressLocation.Notification,
                title: "Plex: Evaluating Weekly Plan...",
                cancellable: false
            }, async () => {
                try {
                    await runPlexCommand(['-m', 'plex.weekly', '--eval', '--file', filePath]);
                    codeLensProvider.refresh();
                    updateStatusBar(editor.document);
                    vscode.window.setStatusBarMessage("$(check) Plex: Weekly plan updated!", 3000);
                } catch (err) {
                    vscode.window.showErrorMessage(`Plex Evaluation Failed: ${err.stderr || err.error?.message}`);
                }
            });
        })
    );

    // Command: plex.exportDaily
    context.subscriptions.push(
        vscode.commands.registerCommand('plex.exportDaily', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) return;
            const filePath = editor.document.uri.fsPath;

            await vscode.window.withProgress({
                location: vscode.ProgressLocation.Notification,
                title: "Plex: Exporting Daily Files...",
                cancellable: false
            }, async () => {
                try {
                    const res = await runPlexCommand(['-m', 'plex.weekly', '--export-daily', '--file', filePath]);
                    const todayStr = new Date().toISOString().slice(0, 10);
                    const todayPath = path.join(getWorkspaceRoot(), 'daily', `${todayStr}.ans`);

                    const items = fs.existsSync(todayPath) ? ["Open Today's File", "View Output"] : ["View Output"];
                    const selection = await vscode.window.showInformationMessage(
                        "Plex: Successfully exported daily files for the week!",
                        ...items
                    );

                    if (selection === "Open Today's File") {
                        const doc = await vscode.workspace.openTextDocument(todayPath);
                        await vscode.window.showTextDocument(doc);
                    } else if (selection === "View Output") {
                        outputChannel.show();
                    }
                } catch (err) {
                    vscode.window.showErrorMessage(`Plex Export Failed: ${err.stderr || err.error?.message}`);
                }
            });
        })
    );

    // Command: plex.exportSingleDay
    context.subscriptions.push(
        vscode.commands.registerCommand('plex.exportSingleDay', async (dateStr) => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) return;
            const filePath = editor.document.uri.fsPath;

            if (!dateStr) {
                vscode.window.showErrorMessage("No target date specified for export.");
                return;
            }

            try {
                await runPlexCommand(['-m', 'plex.weekly', '--export-daily', dateStr, '--file', filePath]);
                const dailyPath = path.join(getWorkspaceRoot(), 'daily', `${dateStr}.ans`);
                const selection = await vscode.window.showInformationMessage(
                    `Plex: Exported daily/${dateStr}.ans!`,
                    "Open File"
                );
                if (selection === "Open File" && fs.existsSync(dailyPath)) {
                    const doc = await vscode.workspace.openTextDocument(dailyPath);
                    await vscode.window.showTextDocument(doc);
                }
            } catch (err) {
                vscode.window.showErrorMessage(`Plex Export Day Failed: ${err.stderr || err.error?.message}`);
            }
        })
    );

    // Command: plex.initWeek
    context.subscriptions.push(
        vscode.commands.registerCommand('plex.initWeek', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) return;
            const filePath = editor.document.uri.fsPath;

            const routines = getRoutinesList();
            const pickItems = routines.map(r => ({
                label: r.label,
                description: r.description,
                routineName: r.routineName
            }));
            pickItems.push({
                label: "$(edit) Custom...",
                description: "Type a custom routine name or script path",
                routineName: null
            });

            const picked = await vscode.window.showQuickPick(pickItems, {
                placeHolder: "Select a routine template or generator to pre-populate this week"
            });

            if (!picked) return;

            let chosenRoutine = picked.routineName;
            if (!chosenRoutine) {
                chosenRoutine = await vscode.window.showInputBox({
                    prompt: "Enter routine template name or generator script path (e.g. school, routines/my_script.py)",
                    value: "school"
                });
                if (!chosenRoutine) return;
            }

            const confirm = await vscode.window.showWarningMessage(
                `Re-initialize week with '${chosenRoutine}'? Existing edits in this weekly file will be overwritten.`,
                "Overwrite & Initialize",
                "Cancel"
            );

            if (confirm !== "Overwrite & Initialize") return;

            await vscode.window.withProgress({
                location: vscode.ProgressLocation.Notification,
                title: `Plex: Initializing Week with '${chosenRoutine}'...`,
                cancellable: false
            }, async () => {
                try {
                    await runPlexCommand(['-m', 'plex.weekly', '--init', chosenRoutine, '--file', filePath, '--overwrite']);
                    codeLensProvider.refresh();
                    vscode.window.showInformationMessage(`Plex: Re-initialized week with ${chosenRoutine}!`);
                } catch (err) {
                    vscode.window.showErrorMessage(`Plex Init Failed: ${err.stderr || err.error?.message}`);
                }
            });
        })
    );

    // Command: plex.insertRoutine
    context.subscriptions.push(
        vscode.commands.registerCommand('plex.insertRoutine', async (targetLine) => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) return;

            const routines = getRoutinesList();
            const pickItems = routines.map(r => ({
                label: r.label,
                description: r.description,
                routineName: r.routineName
            }));

            const picked = await vscode.window.showQuickPick(pickItems, {
                placeHolder: "Select a routine to insert"
            });

            if (!picked) return;

            const lineToInsert = typeof targetLine === 'number' ? targetLine : editor.selection.active.line;
            const insertText = `{${picked.routineName}}\n`;

            await editor.edit(editBuilder => {
                editBuilder.insert(new vscode.Position(lineToInsert, 0), insertText);
            });

            await editor.document.save();
        })
    );

    // Command: plex.runDaily
    context.subscriptions.push(
        vscode.commands.registerCommand('plex.runDaily', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) return;
            const filePath = editor.document.uri.fsPath;

            await vscode.window.withProgress({
                location: vscode.ProgressLocation.Notification,
                title: "Plex: Running Daily Schedule Engine...",
                cancellable: false
            }, async () => {
                try {
                    await runPlexCommand(['-m', 'plex', '--filename', filePath]);
                    vscode.window.setStatusBarMessage("$(check) Plex: Daily schedule calculated!", 3000);
                } catch (err) {
                    vscode.window.showErrorMessage(`Plex Daily Failed: ${err.stderr || err.error?.message}`);
                }
            });
        })
    );

    // Command: plex.pushCalendar
    context.subscriptions.push(
        vscode.commands.registerCommand('plex.pushCalendar', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) return;
            const filePath = editor.document.uri.fsPath;

            await vscode.window.withProgress({
                location: vscode.ProgressLocation.Notification,
                title: "Plex: Pushing Schedule to Google Calendar...",
                cancellable: false
            }, async () => {
                try {
                    await runPlexCommand(['-m', 'plex', '--push', '--filename', filePath]);
                    vscode.window.showInformationMessage("Plex: Schedule pushed to Google Calendar & Notion!");
                } catch (err) {
                    vscode.window.showErrorMessage(`Plex Calendar Push Failed: ${err.stderr || err.error?.message}`);
                }
            });
        })
    );

    // Command: plex.showDayInfo
    context.subscriptions.push(
        vscode.commands.registerCommand('plex.showDayInfo', (dayName, dateStr) => {
            vscode.window.showInformationMessage(`Plex: Day ${dayName} (${dateStr || 'undated'})`);
        })
    );

    // Command: plex.planCommute
    context.subscriptions.push(
        vscode.commands.registerCommand('plex.planCommute', async (uri) => {
            let document;
            if (uri && uri.fsPath) {
                document = await vscode.workspace.openTextDocument(uri);
            } else if (vscode.window.activeTextEditor) {
                document = vscode.window.activeTextEditor.document;
            } else {
                vscode.window.showWarningMessage("Plex: Please open a daily schedule file (*.ans) first.");
                return;
            }

            openCommutePlannerPanel(context, document);
        })
    );
}

let activeCommutePanel = null;

function getPlexConfig() {
    const configDir = process.env.PLEX_CONFIG_DIR || path.join(process.env.HOME || process.env.USERPROFILE, '.config', 'plex');
    const configFile = path.join(configDir, 'config.json');
    if (fs.existsSync(configFile)) {
        try {
            return JSON.parse(fs.readFileSync(configFile, 'utf8'));
        } catch (e) {
            return {};
        }
    }
    return {};
}

function savePlexLocation(name, address) {
    const configDir = process.env.PLEX_CONFIG_DIR || path.join(process.env.HOME || process.env.USERPROFILE, '.config', 'plex');
    const configFile = path.join(configDir, 'config.json');
    let cfg = {};
    if (fs.existsSync(configFile)) {
        try {
            cfg = JSON.parse(fs.readFileSync(configFile, 'utf8'));
        } catch (e) {
            cfg = {};
        }
    }
    if (!cfg.locations) {
        cfg.locations = {};
    }
    const cleanName = name.startsWith('@') ? name : '@' + name;
    cfg.locations[cleanName] = address;
    try {
        fs.mkdirSync(configDir, { recursive: true });
        fs.writeFileSync(configFile, JSON.stringify(cfg, null, 2), { mode: 0o600 });
    } catch (e) {
        console.error("Failed to save location to config.json:", e);
    }
}

function parseDailyPlanFromContent(text) {
    const lines = text.split('\n');
    const tasks = [];
    const commutes = [];
    const planItems = [];
    const emojiToMode = { '🚗': 'drive', '🚇': 'transit', '🚲': 'bike', '🚶': 'walk' };

    const commuteRegex = /^(@\S+)\s*→\s*(@\S+)(?:\s*\|([^|]+)\|)?\s*\[([^\]]+)\]\s*([🚗🚇🚲🚶])(?:\s*\/\/\{::commute::\}|\s*\/\/\s*\{::commute::\})?/u;
    const legacyCommuteRegex = /^commute to\s+(.+?)(?:\s*\|([^|]+)\|)?\s*\[([^\]]+)\]\s*([🚗🚇🚲🚶])?(?:\s*\/\/\s*(@\S+)\s*→\s*(@\S+))?/u;
    const taskRegex = /^([^\n[|]+?)(?:\s*\|([^|]+)\|)?\s*\[([^\]]+)\](?:\s*\(([^)]+)\))?(?:\s*(@\S+))?/;

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i].trim();
        if (!line) continue;
        if (line.startsWith('-------------')) break;

        const cMatch = line.match(commuteRegex);
        if (cMatch) {
            const cObj = {
                fromLoc: cMatch[1],
                toLoc: cMatch[2],
                uuid: cMatch[3] ? cMatch[3].trim() : null,
                duration: cMatch[4],
                mode: emojiToMode[cMatch[5]] || 'drive',
                emoji: cMatch[5]
            };
            commutes.push(cObj);
            planItems.push({
                type: 'commute',
                fromLoc: cObj.fromLoc,
                toLoc: cObj.toLoc,
                uuid: cObj.uuid,
                duration: cObj.duration,
                mode: cObj.mode
            });
            continue;
        }

        const lMatch = line.match(legacyCommuteRegex);
        if (lMatch) {
            const cObj = {
                fromLoc: lMatch[5] || '@Origin',
                toLoc: lMatch[6] || '@Destination',
                uuid: lMatch[2] ? lMatch[2].trim() : null,
                duration: lMatch[3],
                mode: emojiToMode[lMatch[4]] || 'drive',
                emoji: lMatch[4] || '🚗'
            };
            commutes.push(cObj);
            planItems.push({
                type: 'commute',
                fromLoc: cObj.fromLoc,
                toLoc: cObj.toLoc,
                uuid: cObj.uuid,
                duration: cObj.duration,
                mode: cObj.mode
            });
            continue;
        }

        const tMatch = line.match(taskRegex);
        if (tMatch) {
            const desc = tMatch[1].trim();
            const uuidVal = tMatch[2] ? tMatch[2].trim() : null;
            const dur = tMatch[3].trim();
            const timeVal = tMatch[4] || null;
            const locVal = tMatch[5] || null;

            let displayLine = desc;
            if (uuidVal) displayLine += ` |${uuidVal}|`;
            displayLine += ` [${dur}]`;
            if (timeVal) displayLine += ` (${timeVal})`;

            const tObj = {
                id: `t_${tasks.length}`,
                text: displayLine,
                name: desc,
                uuid: uuidVal,
                duration: dur,
                time: timeVal,
                location: locVal,
                address: null
            };
            tasks.push(tObj);
            planItems.push({
                type: 'task',
                task: tObj
            });
        } else {
            const rawObj = {
                id: `t_${tasks.length}`,
                text: line,
                name: line,
                uuid: null,
                duration: '',
                time: null,
                location: null,
                address: null
            };
            tasks.push(rawObj);
            planItems.push({
                type: 'task',
                task: rawObj
            });
        }
    }
    return { tasks, commutes, planItems };
}

async function updateDocumentContentAboveSplitter(document, newContentAboveSplitter) {
    const text = document.getText();
    const lines = text.split('\n');
    let splitterIdx = -1;
    for (let i = 0; i < lines.length; i++) {
        if (lines[i].startsWith('-------------')) {
            splitterIdx = i;
            break;
        }
    }

    let remainder = '';
    if (splitterIdx !== -1) {
        remainder = lines.slice(splitterIdx).join('\n');
    } else {
        remainder = '-------------\n';
    }

    const cleanNew = newContentAboveSplitter.replace(/\r\n/g, '\n').replace(/-------------\s*$/, '').trimEnd();
    const fullNew = cleanNew + '\n\n' + remainder;

    if (fullNew === text) return;

    const edit = new vscode.WorkspaceEdit();
    const fullRange = new vscode.Range(
        document.positionAt(0),
        document.positionAt(text.length)
    );
    edit.replace(document.uri, fullRange, fullNew);
    await vscode.workspace.applyEdit(edit);
}

function openCommutePlannerPanel(context, document) {
    const fileName = path.basename(document.fileName);

    if (activeCommutePanel) {
        activeCommutePanel.title = `Routes: ${fileName}`;
        activeCommutePanel.reveal(vscode.ViewColumn.Beside);
    } else {
        activeCommutePanel = vscode.window.createWebviewPanel(
            'plexCommutePlanner',
            `Routes: ${fileName}`,
            vscode.ViewColumn.Beside,
            {
                enableScripts: true,
                retainContextWhenHidden: true
            }
        );

        activeCommutePanel.onDidDispose(() => {
            activeCommutePanel = null;
        }, null, context.subscriptions);

        const htmlPath = path.join(context.extensionPath, 'media', 'commute_planner.html');
        if (fs.existsSync(htmlPath)) {
            activeCommutePanel.webview.html = fs.readFileSync(htmlPath, 'utf8');
        } else {
            vscode.window.showErrorMessage(`Plex: Cannot find webview template at ${htmlPath}`);
            return;
        }

        activeCommutePanel.webview.onDidReceiveMessage(async (message) => {
            if (!message) return;
            switch (message.command) {
                case 'ready': {
                    sendInitDataToWebview(document);
                    break;
                }
                case 'updateDocument': {
                    if (message.content) {
                        await updateDocumentContentAboveSplitter(document, message.content);
                    }
                    break;
                }
                case 'savePreset': {
                    if (message.name && message.address) {
                        savePlexLocation(message.name, message.address);
                    }
                    break;
                }
            }
        }, null, context.subscriptions);
    }

    function sendInitDataToWebview(doc) {
        if (!activeCommutePanel) return;
        const config = getPlexConfig();
        const parsed = parseDailyPlanFromContent(doc.getText());
        activeCommutePanel.webview.postMessage({
            command: 'init',
            fileName: path.basename(doc.fileName),
            tasks: parsed.tasks,
            commutes: parsed.commutes,
            planItems: parsed.planItems,
            configLocations: config.locations || {},
            bufferFactor: config.routes?.buffer_multiplier || 1.25,
            defaultMode: config.routes?.default_mode || 'drive'
        });
    }

    sendInitDataToWebview(document);
}

function deactivate() {
    if (outputChannel) {
        outputChannel.dispose();
    }
}

module.exports = {
    activate,
    deactivate
};
