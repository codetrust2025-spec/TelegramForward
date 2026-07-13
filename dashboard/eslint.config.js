import react from 'eslint-plugin-react'
import hooks from 'eslint-plugin-react-hooks'

export default [{ files: ['src/components/RecruitmentMailPanel.jsx'], languageOptions: { ecmaVersion: 2022, sourceType: 'module', parserOptions: { ecmaFeatures: { jsx: true } }, globals: { window: 'readonly', document: 'readonly', sessionStorage: 'readonly', fetch: 'readonly', CustomEvent: 'readonly' } }, plugins: { react, 'react-hooks': hooks }, settings: { react: { version: '18.3' } }, rules: { ...hooks.configs.recommended.rules, 'react/jsx-key': 'error', 'react/no-unknown-property': 'error' } }]
