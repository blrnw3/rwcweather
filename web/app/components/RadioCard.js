import { Box, useRadio } from "@chakra-ui/react"

// 1. Create a component that consumes the `useRadio` hook
export default function RadioCard(props) {
    const { getInputProps, getCheckboxProps } = useRadio(props)
  
    const input = getInputProps()
    const checkbox = getCheckboxProps()
  
    return (
      <Box as="label">
        <input {...input} />
        <Box
          {...checkbox}
          {...props.box}
          cursor="pointer"
          borderWidth="1px"
          borderRadius="md"
          boxShadow="md"
          _checked={{
            bg: "pliny.400",
            color: "white",
            borderColor: "pliny.100",
          }}
          _focus={{
            boxShadow: "outline",
          }}
          px={props.px || {base: 2, md: 3, lg: 5}}
          py={props.py || {base: 1, md: 2, lg: 3}}
        >
          {props.children}
        </Box>
      </Box>
    )
  }
  