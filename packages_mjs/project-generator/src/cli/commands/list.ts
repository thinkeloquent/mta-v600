/**
 * The 'list' command for listing available templates and presets.
 */

import { Command } from 'commander';
import pc from 'picocolors';
import { listProjectTypes } from '../../generators/index.js';
import { PRESETS } from '../../presets/index.js';
import { logger } from '../../utils/logger.js';

/**
 * Create the 'list' command.
 */
export function createListCommand(): Command {
  const command = new Command('list')
    .description('List available templates and presets')
    .option('--presets', 'List presets only')
    .option('--templates', 'List templates only')
    .action((options: { presets?: boolean; templates?: boolean }) => {
      const showAll = !options.presets && !options.templates;

      if (showAll || options.templates) {
        console.log();
        console.log(pc.bold(pc.cyan('Project Templates:')));
        console.log();

        const types = listProjectTypes();
        for (const type of types) {
          console.log(`  ${pc.green(type.type.padEnd(18))} ${type.description}`);
        }
        console.log();
      }

      if (showAll || options.presets) {
        console.log(pc.bold(pc.cyan('Presets:')));
        console.log();

        for (const [key, preset] of Object.entries(PRESETS)) {
          console.log(`  ${pc.green(key.padEnd(18))} ${preset.description}`);
        }
        console.log();
      }

      if (showAll) {
        console.log(pc.dim('Usage:'));
        console.log(pc.dim('  polynx create <type> <name>     Create a new project'));
        console.log(pc.dim('  polynx init <preset> [args...]  Run a preset tool'));
        console.log();
      }
    });

  return command;
}
