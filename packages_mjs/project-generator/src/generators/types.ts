/**
 * Type definitions for project generators.
 */

/**
 * Supported project types.
 */
export type ProjectType =
  | 'fastapi'
  | 'fastify'
  | 'frontend'
  | 'react-component'
  | 'ts-package'
  | 'py-package'
  | 'health-check-provider';

/**
 * Options for project generation.
 */
export interface GeneratorOptions {
  /** The project name (kebab-case) */
  name: string;
  /** The target directory for the generated project */
  targetDir: string;
  /** Include a frontend app (for backend projects) */
  withFrontend?: boolean;
  /** The port for the server (for backend projects) */
  port?: number;
  /** Callback for file creation */
  onFileCreate?: (filePath: string) => void;
  /** Allow generating into an existing directory */
  allowExisting?: boolean;
}

/**
 * Result of project generation.
 */
export interface GeneratorResult {
  /** Whether the generation was successful */
  success: boolean;
  /** The path to the generated project */
  projectPath: string;
  /** Error message if generation failed */
  error?: string;
  /** Post-generation instructions */
  instructions?: string[];
}

/**
 * Project generator interface.
 */
export interface ProjectGenerator {
  /** The project type */
  type: ProjectType;
  /** Human-readable name */
  displayName: string;
  /** Description of the project type */
  description: string;
  /** Generate the project */
  generate(options: GeneratorOptions): Promise<GeneratorResult>;
}

/**
 * Configuration for each project type.
 */
export interface ProjectTypeConfig {
  type: ProjectType;
  displayName: string;
  description: string;
  targetDirectory: (rootDir: string, projectName: string) => string;
  templatePath: string;
  allowExisting?: boolean;
}

/**
 * Mapping of project types to their configurations.
 */
export const PROJECT_TYPE_CONFIGS: Record<ProjectType, ProjectTypeConfig> = {
  fastapi: {
    type: 'fastapi',
    displayName: 'FastAPI Backend',
    description: 'Python REST API with FastAPI framework',
    targetDirectory: (rootDir, name) => `${rootDir}/fastapi_apps/${name.replace(/-/g, '_')}`,
    templatePath: 'fastapi-apps-simple/template',
  },
  fastify: {
    type: 'fastify',
    displayName: 'Fastify Backend',
    description: 'Node.js REST API with Fastify framework',
    targetDirectory: (rootDir, name) => `${rootDir}/fastify_apps/${name.replace(/-/g, '_')}`,
    templatePath: 'fastify-apps-simple/template',
  },
  frontend: {
    type: 'frontend',
    displayName: 'React Frontend',
    description: 'React frontend with Vite and Tailwind CSS',
    targetDirectory: (rootDir, name) => `${rootDir}/frontend_apps/${name}`,
    templatePath: 'frontend-apps-simple/template',
  },
  'react-component': {
    type: 'react-component',
    displayName: 'React Component Package',
    description: 'Reusable React UI component package',
    targetDirectory: (rootDir, name) => `${rootDir}/packages_mjs/${name}`,
    templatePath: 'react-ui-component/template',
  },
  'ts-package': {
    type: 'ts-package',
    displayName: 'TypeScript Package',
    description: 'TypeScript package under @internal/* scope',
    targetDirectory: (rootDir, name) => `${rootDir}/packages_mjs/${name}`,
    templatePath: 'ts-package/template',
  },
  'py-package': {
    type: 'py-package',
    displayName: 'Python Package',
    description: 'Python package under packages_py/*',
    targetDirectory: (rootDir, name) => `${rootDir}/packages_py/${name.replace(/-/g, '_')}`,
    templatePath: 'py-package/template',
  },
  'health-check-provider': {
    type: 'health-check-provider',
    displayName: 'Health Check Provider',
    description: 'New provider for provider_api_getters',
    targetDirectory: (rootDir, name) => rootDir,
    templatePath: 'health-check-provider/template',
    allowExisting: true,
  },
};
