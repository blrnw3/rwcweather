import { Link } from "@chakra-ui/react";
import { BiLinkExternal } from "react-icons/bi";
import { IconContext } from "react-icons/lib";

export function RwcExternalLink(props) {
    return <Link isExternal href={props.href}>
        {props.children}&nbsp;
        <IconContext.Provider value={{ style: {display: "inline"} }} >
            <BiLinkExternal />
        </IconContext.Provider>
    </Link>
}
