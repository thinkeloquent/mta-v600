/**
 * The 'init' command for running preset tools.
 */

import { Command } from 'commander';
import * as p from '@clack/prompts';
import pc from 'picocolors';
import { PRESETS, type PresetName } from '../../presets/index.js';
import { logger } from '../../utils/logger.js';

/**
 * Create the 'init' command.
 */
export function createInitCommand(): Command {
  const command = new Command('init')
    .description('Initialize with a preset tool')
    .argument('<preset>', 'Preset name (degit, vite, nx-workspace, nx)')
    .argument('[args...]', 'Arguments to pass to the preset')
    .action(async (preset: string, args: string[]) => {
      const presetName = preset as PresetName;

      if (!(presetName in PRESETS)) {
        logger.error(`Unknown preset: ${preset}`);
        logger.info(`Available presets: ${Object.keys(PRESETS).join(', ')}`);
        process.exit(1);
      }

      p.intro(pc.bgCyan(pc.black(` Running ${PRESETS[presetName].name} `)));

      const presetConfig = PRESETS[presetName];
      let result;

      switch (presetName) {
        case 'degit': {
          const [repo, dest] = args;
          if (!repo || !dest) {
            logger.error('Usage: polynx init degit <repo> <dest>');
            process.exit(1);
          }
          result = await presetConfig.run(repo, dest);
          break;
        }
        case 'vite': {
          const [projectName, template] = args;
          if (!projectName) {
            logger.error('Usage: polynx init vite <project-name> [template]');
            process.exit(1);
          }
          result = await (presetConfig.run as (name: string, template?: string) => Promise<{ success: boolean; error?: string }>)(projectName, template);
          break;
        }
        case 'nx-workspace': {
          const [workspaceName, preset] = args;
          if (!workspaceName) {
            logger.error('Usage: polynx init nx-workspace <workspace-name> [preset]');
            process.exit(1);
          }
          result = await (presetConfig.run as (name: string, preset?: string) => Promise<{ success: boolean; error?: string }>)(workspaceName, preset);
          break;
        }
        case 'nx': {
          result = await (presetConfig.run as () => Promise<{ success: boolean; error?: string }>)();
          break;
        }
        default: {
          logger.error(`Preset not implemented: ${preset}`);
          process.exit(1);
        }
      }

      if (!result.success) {
        p.log.error(result.error || 'Preset command failed');
        process.exit(1);
      }

      p.outro(pc.green('Done!'));
    });

  return command;
}
