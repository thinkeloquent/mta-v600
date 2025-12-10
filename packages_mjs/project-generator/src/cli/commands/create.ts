/**
 * The 'create' command for generating projects.
 */

import { Command } from 'commander';
import * as p from '@clack/prompts';
import pc from 'picocolors';
import { generate, listProjectTypes } from '../../generators/index.js';
import type { ProjectType } from '../../generators/types.js';
import { validateFullProjectName } from '../../core/validators.js';
import { runInteractive, withSpinner, showPostCreateInstructions, PROJECT_TYPES } from '../interactive.js';
import { logger } from '../../utils/logger.js';

/**
 * Create the 'create' command.
 */
export function createCreateCommand(): Command {
  const command = new Command('create')
    .description('Create a new project')
    .argument('[type]', 'Project type (fastapi, fastify, frontend, react-component, ts-package, py-package)')
    .argument('[name]', 'Project name (kebab-case)')
    .option('--with-frontend', 'Include a frontend app (for backend projects)')
    .option('--port <port>', 'Server port (for backend projects)', parseInt)
    .action(async (type?: string, name?: string, options?: { withFrontend?: boolean; port?: number }) => {
      // If no arguments, run interactive mode
      if (!type && !name) {
        const answers = await runInteractive();
        if (!answers) {
          process.exit(0);
        }

        await executeCreate(answers.projectType, answers.projectName, answers.options);
        return;
      }

      // Validate type
      const validTypes: ProjectType[] = ['fastapi', 'fastify', 'frontend', 'react-component', 'ts-package', 'py-package'];
      if (!type || !validTypes.includes(type as ProjectType)) {
        logger.error(`Invalid project type: ${type}`);
        logger.info(`Valid types: ${validTypes.join(', ')}`);
        process.exit(1);
      }

      // Validate name
      if (!name) {
        logger.error('Project name is required');
        process.exit(1);
      }

      const validation = validateFullProjectName(name);
      if (!validation.valid) {
        logger.error(validation.error!);
        process.exit(1);
      }

      await executeCreate(type as ProjectType, name, options || {});
    });

  return command;
}

/**
 * Execute the create command.
 */
async function executeCreate(
  projectType: ProjectType,
  projectName: string,
  options: Record<string, unknown>
): Promise<void> {
  p.intro(pc.bgCyan(pc.black(' PolyNx Project Generator ')));

  const result = await withSpinner(
    `Creating ${projectType} project: ${projectName}`,
    async () => {
      return generate(projectType, {
        name: projectName,
        targetDir: '',
        withFrontend: options.withFrontend as boolean,
        port: options.port as number,
        onFileCreate: (filePath) => {
          logger.file(filePath);
        },
      });
    }
  );

  if (!result.success) {
    p.log.error(result.error || 'Unknown error');
    process.exit(1);
  }

  showPostCreateInstructions(projectType, projectName, result.projectPath);
}
