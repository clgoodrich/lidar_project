---
name: Do not revert user edits
description: Never rebuild presentation from scratch or overwrite user's manual changes to the pptx — only modify what was explicitly asked for
type: feedback
---

Do not revert user's manual edits to the presentation or other files. When rebuilding the presentation, only change what the user explicitly asked for in the current prompt.

**Why:** User has been manually editing the pptx between rebuilds, and full rebuilds from the script overwrite those changes every time. This has happened repeatedly and is very frustrating.

**How to apply:** When the user asks for a specific change, make only that change. If the build script regenerates everything, be aware that running it will overwrite manual edits. Warn the user or find a way to make targeted changes instead of full rebuilds.
