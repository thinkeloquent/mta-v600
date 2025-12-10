/**
 * Logger utilities with colored output.
 */

import pc from 'picocolors';

export const logger = {
  /** Log an info message */
  info(message: string): void {
    console.log(pc.cyan('ℹ'), message);
  },

  /** Log a success message */
  success(message: string): void {
    console.log(pc.green('✓'), message);
  },

  /** Log a warning message */
  warn(message: string): void {
    console.log(pc.yellow('⚠'), message);
  },

  /** Log an error message */
  error(message: string): void {
    console.log(pc.red('✗'), message);
  },

  /** Log a file creation */
  file(filePath: string): void {
    console.log(pc.dim('  +'), pc.dim(filePath));
  },

  /** Log a step in a process */
  step(step: number, total: number, message: string): void {
    console.log(pc.dim(`[${step}/${total}]`), message);
  },

  /** Log a blank line */
  blank(): void {
    console.log();
  },

  /** Log a header */
  header(message: string): void {
    console.log();
    console.log(pc.bold(pc.cyan(message)));
    console.log();
  },

  /** Log a divider */
  divider(): void {
    console.log(pc.dim('─'.repeat(50)));
  },
};
