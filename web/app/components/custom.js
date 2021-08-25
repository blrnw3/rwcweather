import { Link } from "@chakra-ui/react";
import { BiLinkExternal } from "react-icons/bi";

export function RwcExternalLink(props) {
    return <Link isExternal href={props.href}>
        {props.children}&nbsp;
        <BiLinkExternal />
    </Link>
}
