/**
 * Shell execution utilities using execa.
 */

import { execa, type Options as ExecaOptions } from 'execa';

export interface ExecResult {
  stdout: string;
  stderr: string;
  exitCode: number;
}

/**
 * Execute a shell command.
 */
export async function exec(
  command: string,
  args: string[] = [],
  options: ExecaOptions = {}
): Promise<ExecResult> {
  const result = await execa(command, args, {
    ...options,
    reject: false,
  });

  return {
    stdout: typeof result.stdout === 'string' ? result.stdout : '',
    stderr: typeof result.stderr === 'string' ? result.stderr : '',
    exitCode: result.exitCode ?? 0,
  };
}

/**
 * Execute a command and stream output to the console.
 */
export async function execStream(
  command: string,
  args: string[] = [],
  options: ExecaOptions = {}
): Promise<number> {
  const result = await execa(command, args, {
    ...options,
    stdio: 'inherit',
    reject: false,
  });

  return result.exitCode ?? 0;
}

/**
 * Check if a command exists.
 */
export async function commandExists(command: string): Promise<boolean> {
  try {
    const result = await execa('which', [command], { reject: false });
    return result.exitCode === 0;
  } catch {
    return false;
  }
}

/**
 * Run npx with a package.
 */
export async function npx(
  pkg: string,
  args: string[] = [],
  options: ExecaOptions = {}
): Promise<number> {
  return execStream('npx', [pkg, ...args], options);
}

/**
 * Run npm create.
 */
export async function npmCreate(
  pkg: string,
  args: string[] = [],
  options: ExecaOptions = {}
): Promise<number> {
  return execStream('npm', ['create', pkg, ...args], options);
}
