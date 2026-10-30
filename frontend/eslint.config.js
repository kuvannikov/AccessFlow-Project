import js from '@eslint/js'
import pluginQuery from '@tanstack/eslint-plugin-query'
import pluginRouter from '@tanstack/eslint-plugin-router'
import boundaries from 'eslint-plugin-boundaries'
import jsxA11y from 'eslint-plugin-jsx-a11y-x'
import reactHooks from 'eslint-plugin-react-hooks'
import { defineConfig, globalIgnores } from 'eslint/config'
import tseslint from 'typescript-eslint'

export default defineConfig(
  globalIgnores(['dist']),
  js.configs.recommended,
  tseslint.configs.strictTypeChecked,
  tseslint.configs.stylisticTypeChecked,
  {
    languageOptions: {
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
  },
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      reactHooks.configs.flat['recommended-latest'],
      jsxA11y.configs.strict,
      pluginQuery.configs['flat/recommended-strict'],
      pluginRouter.configs['flat/recommended'],
    ],
  },
  {
    files: ['src/**/*.{ts,tsx}'],
    plugins: { boundaries },
    settings: {
      'import/resolver': { typescript: { project: './tsconfig.app.json' } },
      'boundaries/elements': [
        { type: 'app', pattern: 'src/app', partialMatch: false },
        { type: 'pages', pattern: 'src/pages', partialMatch: false },
        { type: 'feature', pattern: 'src/features/*', partialMatch: false, capture: ['name'] },
        { type: 'shared', pattern: 'src/shared', partialMatch: false },
      ],
    },
    rules: {
      'boundaries/no-unknown-files': 'error',
      'boundaries/dependencies': [
        'error',
        {
          default: 'disallow',
          checkUnknownLocals: true,
          policies: [
            {
              from: { element: { type: 'app' } },
              allow: { to: { element: { types: { anyOf: ['pages', 'feature', 'shared'] } } } },
            },
            {
              from: { element: { type: 'pages' } },
              allow: { to: { element: { types: { anyOf: ['feature', 'shared'] } } } },
            },
            {
              from: { element: { type: 'feature' } },
              allow: { to: { element: { type: 'shared' } } },
            },
          ],
        },
      ],
    },
  },
  {
    files: ['**/*.js'],
    extends: [tseslint.configs.disableTypeChecked],
  },
)
