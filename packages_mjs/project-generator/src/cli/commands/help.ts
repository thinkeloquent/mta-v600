/**
 * The 'help' command with optional Gemini AI integration.
 */

import { Command } from 'commander';
import pc from 'picocolors';
import { logger } from '../../utils/logger.js';

/**
 * Create the 'help' command.
 */
export function createHelpCommand(): Command {
  const command = new Command('help')
    .description('Get help with polynx commands')
    .argument('[command]', 'Command to get help for')
    .option('--ai <question>', 'Ask Gemini AI for help')
    .action(async (cmd?: string, options?: { ai?: string }) => {
      if (options?.ai) {
        await showAiHelp(options.ai);
        return;
      }

      if (cmd) {
        showCommandHelp(cmd);
      } else {
        showGeneralHelp();
      }
    });

  return command;
}

/**
 * Show general help.
 */
function showGeneralHelp(): void {
  console.log();
  console.log(pc.bold(pc.cyan('PolyNx Project Generator')));
  console.log();
  console.log('A CLI tool for scaffolding projects in polyglot Nx-powered monorepos.');
  console.log();
  console.log(pc.bold('Commands:'));
  console.log();
  console.log(`  ${pc.green('create')}           Create a new project`);
  console.log(`  ${pc.green('init')}             Run a preset tool (degit, vite, nx)`);
  console.log(`  ${pc.green('list')}             List available templates and presets`);
  console.log(`  ${pc.green('help')}             Show this help message`);
  console.log();
  console.log(pc.bold('Examples:'));
  console.log();
  console.log(pc.dim('  # Interactive mode'));
  console.log('  polynx create');
  console.log();
  console.log(pc.dim('  # Create a FastAPI backend'));
  console.log('  polynx create fastapi user-service');
  console.log();
  console.log(pc.dim('  # Create a Fastify backend'));
  console.log('  polynx create fastify api-gateway');
  console.log();
  console.log(pc.dim('  # Create a React frontend'));
  console.log('  polynx create frontend dashboard');
  console.log();
  console.log(pc.dim('  # Create a TypeScript package'));
  console.log('  polynx create ts-package utils');
  console.log();
  console.log(pc.dim('  # Use a preset'));
  console.log('  polynx init vite my-app');
  console.log('  polynx init nx');
  console.log();
  console.log(pc.dim('  # Ask Gemini AI for help'));
  console.log('  polynx help --ai "how do I add a new route to fastapi?"');
  console.log();
}

/**
 * Show help for a specific command.
 */
function showCommandHelp(cmd: string): void {
  switch (cmd) {
    case 'create':
      console.log();
      console.log(pc.bold(pc.cyan('polynx create')));
      console.log();
      console.log('Create a new project from a template.');
      console.log();
      console.log(pc.bold('Usage:'));
      console.log('  polynx create                           Interactive mode');
      console.log('  polynx create <type> <name>             Create with type and name');
      console.log('  polynx create <type> <name> --option    Create with options');
      console.log();
      console.log(pc.bold('Project Types:'));
      console.log('  fastapi         Python REST API with FastAPI');
      console.log('  fastify         Node.js REST API with Fastify');
      console.log('  frontend        React frontend with Vite + Tailwind');
      console.log('  react-component Reusable React UI component');
      console.log('  ts-package      TypeScript package (@internal/*)');
      console.log('  py-package      Python package (packages_py/*)');
      console.log();
      console.log(pc.bold('Options:'));
      console.log('  --with-frontend Include a frontend (for backend projects)');
      console.log('  --port <port>   Server port (for backend projects)');
      console.log();
      break;

    case 'init':
      console.log();
      console.log(pc.bold(pc.cyan('polynx init')));
      console.log();
      console.log('Initialize a project using preset tools.');
      console.log();
      console.log(pc.bold('Usage:'));
      console.log('  polynx init degit <repo> <dest>         Clone a repo template');
      console.log('  polynx init vite <name> [template]      Create Vite project');
      console.log('  polynx init nx-workspace <name> [preset] Create Nx workspace');
      console.log('  polynx init nx                          Add Nx to existing project');
      console.log();
      break;

    case 'list':
      console.log();
      console.log(pc.bold(pc.cyan('polynx list')));
      console.log();
      console.log('List available templates and presets.');
      console.log();
      console.log(pc.bold('Options:'));
      console.log('  --templates     List templates only');
      console.log('  --presets       List presets only');
      console.log();
      break;

    default:
      logger.error(`Unknown command: ${cmd}`);
      logger.info('Run "polynx help" for available commands');
  }
}

/**
 * Show AI-powered help using Gemini.
 */
async function showAiHelp(question: string): Promise<void> {
  const apiKey = process.env.GEMINI_API_KEY;

  if (!apiKey) {
    logger.warn('GEMINI_API_KEY not set. AI help is not available.');
    logger.info('Set GEMINI_API_KEY environment variable to enable AI help.');
    return;
  }

  logger.info('Asking Gemini AI...');
  console.log();

  try {
    const response = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${apiKey}`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          contents: [
            {
              parts: [
                {
                  text: `You are a helpful assistant for the PolyNx project generator CLI.
The CLI supports:
- Creating FastAPI (Python) and Fastify (Node.js) backend apps
- Creating React frontend apps with Vite and Tailwind
- Creating React component packages
- Creating TypeScript packages under @internal/*
- Creating Python packages under packages_py/*
- Using presets like degit, create-vite, create-nx-workspace, and nx init

The monorepo structure is:
- fastapi_apps/ - Python FastAPI apps (use underscores in folder names)
- fastify_apps/ - Node.js Fastify apps (use underscores in folder names)
- frontend_apps/ - React frontend apps
- packages_mjs/ - TypeScript packages
- packages_py/ - Python packages

Answer the following question concisely:
${question}`,
                },
              ],
            },
          ],
        }),
      }
    );

    const data = await response.json();
    const answer = data.candidates?.[0]?.content?.parts?.[0]?.text;

    if (answer) {
      console.log(pc.dim('─'.repeat(50)));
      console.log();
      console.log(answer);
      console.log();
      console.log(pc.dim('─'.repeat(50)));
    } else {
      logger.error('No response from Gemini AI');
    }
  } catch (error) {
    logger.error(`Failed to get AI help: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}
