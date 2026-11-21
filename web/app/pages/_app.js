import { useEffect } from 'react'
import { useRouter } from 'next/router'
import { ChakraProvider, ColorModeProvider } from '@chakra-ui/react'

import theme from '../_theme'
import { disableGa, hasOptOutCookie, pageview } from '../lib/ga'

function MyApp({ Component, pageProps }) {
  const router = useRouter()

  useEffect(() => {
    if (hasOptOutCookie()) {
      disableGa()
    }
    const handle = (url) => {
      pageview(url)
    }
    router.events.on('routeChangeComplete', handle)
    return () => {
      router.events.off('routeChangeComplete', handle)
    }
  }, [router.events])

  return (
    <ChakraProvider resetCSS theme={theme}>
      <ColorModeProvider
        options={{
          useSystemColorMode: true,
        }}
      >
        <Component {...pageProps} />
      </ColorModeProvider>
    </ChakraProvider>
  )
}

export default MyApp
