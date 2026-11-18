import { defineConfig } from 'eslint/config';
import angular from 'angular-eslint';
import ts from 'typescript-eslint';

export default defineConfig([
  { ignores: ['src/app/core/api.generated.ts'] },
  {
    files: ['src/**/*.ts'],
    extends: [...ts.configs.recommended, ...angular.configs.tsRecommended],
    processor: angular.processInlineTemplates,
  },
  {
    files: ['src/**/*.html'],
    extends: [...angular.configs.templateRecommended, ...angular.configs.templateAccessibility],
  },
]);
