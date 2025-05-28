# CodeLLM Bridge

A powerful utility for seamlessly transferring code between your local codebase and AI tools like ChatGPT, Gemini, Grok, and others.

## About

CodeLLM Bridge was developed to simplify the workflow between AI tools and your coding environment. It allows you to:

1. Select and copy relevant parts of your codebase into LLMs (ChatGPT, Gemini, Grok, etc.)
2. Get AI-generated changes
3. Implement those changes using tools like Cursor.ai or Windsurf

This tool bridges the gap between your development environment and AI coding assistants, making it easier to leverage AI while maintaining control over your codebase.

## Why This Workflow?

This workflow addresses a fundamental limitation of AI coding assistants like Cursor and Windsurf:

**Context Window Limitations:** Tools like Cursor and Windsurf have restricted context windows that only allow them to process small chunks of code at a time to reduce operational costs. This limitation means they often lack the full context needed to make good suggestions, frequently resulting in broken code.

**Whole-Codebase Understanding:** In contrast, models like ChatGPT, Gemini, and Grok allow you to paste in larger amounts of code, giving them a more comprehensive view of your codebase. This broader context enables them to make more accurate and cohesive recommendations.

With CodeLLM Bridge, you get the best of both worlds:
- Use larger models to analyze your code holistically and suggest changes
- Use specialized coding tools like Cursor or Windsurf to implement those changes

While you can use Cursor or Windsurf directly for small, isolated changes in simple files, this two-step approach provides much better results for complex codebases or substantial modifications.

## Default Meta Prompt

CodeLLM Bridge comes with a default meta prompt that instructs AI models to provide code and edits directly in the chat interface rather than in code editors or canvases. This is crucial because:

1. **Usability Issues:** When AI models present code in their built-in editors or canvases, it can be difficult to copy that content into your actual coding environment.

2. **Implementation Challenges:** Code presented in editors often lacks the context needed for implementation (like file paths or specific locations for changes).

3. **Compatibility with AI Code Editors:** When using tools like Cursor or Windsurf to implement changes, they work better with clearly formatted code instructions in plain text rather than editor-formatted code.

The default prompt encourages AI models to provide clear instructions about which files to modify, where changes should be made, and how the code should be formatted - all within the chat interface for easy copying.

## Features

- **File Tree Selection**: Choose specific files and directories to share with the AI
- **File Content Copying**: Automatically formats the content of selected files
- **Meta Prompts**: Save and reuse common instructions for AI tools
- **Custom Instructions**: Add specific guidance for each interaction
- **Profile Management**: Create and switch between different configurations 
- **History Tracking**: Save and recall previous copy operations
- **Smart Ignore Patterns**: Comes with preconfigured ignore patterns for common system folders, temporary files, and binaries
  - Automatically configured on first launch with sensible defaults
  - Excludes: node_modules, build directories, cache folders, IDE settings, media files, etc.
  - Fully customizable to fit your project needs
  - Helps keep the context focused on relevant code
- **Theme Support**: Choose between light and dark themes
- **Full File Tree Option**: Copy the entire directory structure regardless of which files are checked
  - Provides a complete overview of your project organization
  - Helps AI models understand the context and relationships between files
  - Useful when you want to show the complete project structure without copying all file contents
- **Temporary File Export**: Save content to a temporary file and copy the file to clipboard
  - Ideal for large codebases that exceed AI input field character limits
  - Creates timestamped temporary files that can be uploaded to AI tools
  - Automatically copies the file to clipboard for easy pasting into applications

## Output Format

When you click "Copy to Clipboard", the tool generates a structured text format that includes:

1. **File Tree Section**: `<file_tree>...</file_tree>`
   - Shows either selected files/folders or the complete directory structure (if "Copy entire file tree" is checked)
   - Displays proper hierarchy with indentation and branch indicators (├── and └──)
   - Uses absolute paths for root directories and relative paths for children

2. **File Contents Section**: `<file_contents>...</file_contents>`
   - Lists the contents of all checked files
   - Each file is formatted as:
     ```
     File: /path/to/file.ext
     ```ext
     [actual file contents]
     ```
     
   - File extensions are automatically detected and included in code blocks for proper syntax highlighting

3. **Meta Prompts Section**: `<meta prompt 1="Title">...</meta prompt 1>`
   - Includes any enabled meta prompts with their titles and contents
   - Helps guide the AI in how to process or respond to your code

4. **User Instructions Section**: `<user_instructions>...</user_instructions>`
   - Contains your specific instructions for the AI

This standardized format helps AI models understand your codebase structure and process your requests more effectively.

## Installation

1. Clone this repository to your local machine
2. Run `Step1_Setup_CodeLLM_Bridge.bat` to set up the Python environment
3. Run `Step2_Run_CodeLLM_Bridge.bat` to launch the application

## How to Use

1. **Add Folders**: Click "Add Folder" to select the root directories containing your code
2. **Select Files**: Double-click on files or folders in the tree to select them
3. **Add Instructions**: Enter specific instructions for the AI in the "User Instructions" section
4. **Add Meta Prompts**: Create reusable prompts for common tasks
5. **Copy to Clipboard**: Click "Copy to Clipboard" to format everything for the AI
   - **Alternative**: Click "Save to Temp File & Copy" to save the content to a temporary file and copy the file to clipboard
   - This is useful for large codebases that exceed AI input field limits - you can paste the file directly into applications
6. **Paste into AI Tool**: Paste the copied content or file into your AI tool of choice
7. **Implement Changes**: When you receive the AI's response, use tools like Cursor.ai or Windsurf to implement the changes

## Workflow

1. Use CodeLLM Bridge to select and copy relevant code
2. Paste the formatted code into your preferred LLM
3. Clearly explain what changes you need
4. Review the AI's suggestions
5. Use Cursor.ai, Windsurf, or your preferred IDE to implement the changes

## License

This software is open source and free to use for non-commercial purposes. Commercial use is prohibited without express permission from Psynect Corp.

## Credits

Developed by [Psynect Corp](https://psynect.ai)

---

© Psynect Corp. All rights reserved. 