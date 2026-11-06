import { resolve } from 'node:path'

import { generateApi } from 'swagger-typescript-api'

await generateApi({
  input: resolve('../openapi/openapi.json'),
  output: resolve('src/generated'),
  name: 'api.ts',
  generateClient: false,
  generateRouteTypes: true,
  typeOnlyImports: true,
})
