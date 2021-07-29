// 1. import `extendTheme` function
import { extendTheme } from "@chakra-ui/react"
import { mode, createBreakpoints } from "@chakra-ui/theme-tools"

// 2. Add your color mode config
const config = {
  initialColorMode: "light",
  useSystemColorMode: false,
}

const breakpoints = createBreakpoints({
    sm: "360px",
    md: "768px",
    lg: "1280px",
    xl: "1680px",
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
      pliny: {
        50: '#fff2da',
        100: '#ffd9ae',
        200: '#ffc17d',
        300: '#ffa94c',
        400: '#ff901a',
        500: '#e67600',
        600: '#b35c00',
        700: '#814100',
        800: '#4f2600',
        900: '#200b00',
      }
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
    global: {
    },
  },
  components: {
    Heading: {
      baseStyle: {
        mt: "1",
        mb: "3"
      },
      sizes: {
        1: {
          fontSize: {base: "xl",  md: "2xl", lg: "3xl"},
          color: "brand.700"
        },
        2: {
          fontSize: {base: "lg",  md: "xl", lg: "2xl"},
          color: "brand.600",
          mb: "2"
        },
        3: {
          fontSize: {base: "lg",  md: "lg", lg: "xl"},
          color: "brand.500"
        },
        4: {
          fontSize: {base: "lg",  md: "lg", lg: "xl"},
          color: "pliny.400",
          fontWeight: "bolder"
        }
      }
    },
    Text: {
      baseStyle: {
        // fontSize: {base: "sm",  md: "md", lg: "lg"},
      },
      sizes: {
        
      },
      variants: {
        para: {
          mb: "3"
        }
      }
    },
    Link: {
      baseStyle: {
        textDecoration: "underline",
        outline: "none",
        color: "pliny.500",
        fontWeight: "medium",
        _hover: {
          textDecoration: "none",
        },
      },
      variants: {
        subtle: {
          textDecoration: "none",
          color: "pliny.700",
          _hover: {
            color: "orange.400",
          },
        },
        hidden: {
          textDecoration: "none",
          color: "inherit",
          _hover: {
            textDecoration: "none",
          },
        }
      },
    }
  }
}


const theme = extendTheme(themeDefault)

export default theme;
