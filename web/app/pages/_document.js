import NextDocument, { Html, Head, Main, NextScript } from 'next/document'
import { gaBootstrapInline } from '../lib/ga'

export default class Document extends NextDocument {
  render() {
    return (
      <Html>
        <Head>
          {process.env.NODE_ENV === 'production' && (
            <script
              dangerouslySetInnerHTML={{
                __html: gaBootstrapInline(),
              }}
            />
          )}
        </Head>
        <body>
          <Main />
          <NextScript />
        </body>
      </Html>
    )
  }
}
