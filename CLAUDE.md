# Project Rules

## No Hallucination
- NEVER assume what the code does. Always read the actual code before making any claim about its behavior.
- NEVER guess variable names, function signatures, column names, or thresholds. Verify every detail by reading the file.
- If you haven't read the relevant section of the code in this conversation, read it before answering or suggesting changes.
- When referencing line numbers, re-read the file to confirm — line numbers shift after edits.

## Verify Everything From the Codebase
- Every statement about what the code does must be backed by a direct read of that code, not memory or assumption.
- Before claiming a label, flag, column, or threshold exists — grep or read to confirm it exists RIGHT NOW in the current code.
- Before claiming something is missing — grep to confirm it is actually missing.
- Do not rely on conversation history for code state. The file on disk is the source of truth.

## Do Not Change Things Without Being Asked
- NEVER make changes the user did not explicitly request.
- Do not refactor, rename, reformat, add comments, or "improve" code on your own initiative.
- Do not fix things you "notice" unless the user asks you to fix them.
- If you spot an issue, REPORT it to the user and wait for their instruction before touching the code.
- One change at a time. Do exactly what was asked, nothing more.

## Fin.py Specific
- This is a production model pipeline. Every change has downstream impact.
- Do NOT change `cons_model_ot()` unless explicitly told to.
- Always check REJECTION_FLAGS, OD rescue list, and modis() when adding new comment labels.
- The user runs this daily — never leave the code in a broken state.
