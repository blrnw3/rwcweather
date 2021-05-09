// 1. import `extendTheme` function
import { extendTheme } from "@chakra-ui/react"
import { mode, createBreakpoints } from "@chakra-ui/theme-tools"

// 2. Add your color mode config
const config = {
  initialColorMode: "light",
  useSystemColorMode: false,
}

const breakpoints = createBreakpoints({
    sm: "320px",
    md: "768px",
    lg: "960px",
    xl: "1200px",
  })

// 2. Extend the theme to include custom colors, fonts, etc
const themeDefault = {
  colors: {
      // https://smart-swatch.netlify.app/#419767
      brand: {
        50: '#e3faef',
        100: '#c5e9d5',
        200: '#a3dabb',
        300: '#81c9a1',
        400: '#5fba87',
        500: '#45a06d',
        600: '#347d54',
        700: '#23593c',
        800: '#113622',
        900: '#001406',
      },
  },
  breakpoints,
  fontSizes: {
    // a: "12em"
  },
  fonts: {
    body: "system-ui, sans-serif",
    heading: "Georgia, serif",
    mono: "Menlo, monospace",
  },
  styles: {
        global: (props) => ({
            a: {
                color: mode("brand.300","brand.600")(props),
            },
        }),
    }
}


const theme = extendTheme(themeDefault)

export default theme;
