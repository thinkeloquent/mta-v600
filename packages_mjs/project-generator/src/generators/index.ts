/**
 * Project generators exports.
 */

export * from './types.js';
export * from './base.js';

import type { ProjectType, GeneratorOptions, GeneratorResult } from './types.js';
import { generateProject } from './base.js';

/**
 * Generate a project of the specified type.
 */
export async function generate(
  projectType: ProjectType,
  options: GeneratorOptions
): Promise<GeneratorResult> {
  return generateProject(projectType, options);
}

/**
 * List all available project types.
 */
export function listProjectTypes(): Array<{ type: ProjectType; name: string; description: string }> {
  return [
    { type: 'fastapi', name: 'FastAPI Backend', description: 'Python REST API with FastAPI' },
    { type: 'fastify', name: 'Fastify Backend', description: 'Node.js REST API with Fastify' },
    { type: 'frontend', name: 'React Frontend', description: 'React + Vite + Tailwind CSS' },
    { type: 'react-component', name: 'React Component', description: 'Reusable React UI component package' },
    { type: 'ts-package', name: 'TypeScript Package', description: '@internal/* TypeScript package' },
    { type: 'py-package', name: 'Python Package', description: 'packages_py/* Python package' },
  ];
}
