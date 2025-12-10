#!/usr/bin/env node

/**
 * PolyNx Project Generator CLI
 *
 * A CLI tool for scaffolding projects in polyglot Nx-powered monorepos.
 *
 * Usage:
 *   polynx create                     Interactive mode
 *   polynx create <type> <name>       Create a project
 *   polynx init <preset> [args...]    Run a preset tool
 *   polynx list                       List templates and presets
 *   polynx help [command]             Get help
 */

import { Command } from 'commander';
import { createCreateCommand, createInitCommand, createListCommand, createHelpCommand } from './cli/commands/index.js';

const program = new Command();

program
  .name('polynx')
  .description('PolyNx Project Generator - Scaffold projects in polyglot monorepos')
  .version('0.2.0');

// Add commands
program.addCommand(createCreateCommand());
program.addCommand(createInitCommand());
program.addCommand(createListCommand());
program.addCommand(createHelpCommand());

// Default action: run interactive mode
program.action(async () => {
  // Import dynamically to avoid loading all dependencies for --help
  const { runInteractive, showPostCreateInstructions, withSpinner } = await import('./cli/interactive.js');
  const { generate } = await import('./generators/index.js');
  const { logger } = await import('./utils/logger.js');

  const answers = await runInteractive();
  if (!answers) {
    process.exit(0);
  }

  const result = await withSpinner(
    `Creating ${answers.projectType} project: ${answers.projectName}`,
    async () => {
      return generate(answers.projectType, {
        name: answers.projectName,
        targetDir: '',
        ...answers.options,
        onFileCreate: (filePath) => {
          logger.file(filePath);
        },
      });
    }
  );

  if (!result.success) {
    const { log } = await import('@clack/prompts');
    log.error(result.error || 'Unknown error');
    process.exit(1);
  }

  showPostCreateInstructions(answers.projectType, answers.projectName, result.projectPath);
});

program.parse();
