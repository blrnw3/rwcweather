import Head from "next/head";
import { Heading, Text, Button } from "@chakra-ui/react";
import { Page } from "../components/Page";
import { isHttpsRequest, serializeOptOutCookie } from "../lib/ga";

export async function getServerSideProps({ req, res, query }) {
    const clear = query.off === "1" || query.off === "true";
    res.setHeader("Set-Cookie", serializeOptOutCookie({
        clear,
        secure: isHttpsRequest(req),
    }));
    return { props: { optedOut: !clear } };
}

export default function NoTrack({ optedOut }) {
    return (
        <Page title={optedOut ? "Analytics off" : "Analytics on"}>
            <Head>
                <meta name="robots" content="noindex, nofollow" />
            </Head>
            {optedOut ? (
                <>
                    <Heading as="h1" size="1">Analytics off</Heading>
                    <Text variant="para" mt="4">
                        This browser will not send visits to Google Analytics. A cookie named
                        {" "}<Text as="code" fontFamily="mono">rwc_no_ga</Text> remembers
                        this choice for about 10 years, on this site only.
                    </Text>
                    <Text variant="para" mt="3">
                        The cookie is checked before the analytics script is loaded, including
                        when moving between pages. Clearing this site&apos;s cookies, or using
                        another browser or device, will turn analytics back on there.
                    </Text>
                    <Button as="a" href="/no-track?off=1" colorScheme="pliny" mt="6">
                        Turn analytics back on
                    </Button>
                </>
            ) : (
                <>
                    <Heading as="h1" size="1">Analytics on</Heading>
                    <Text variant="para" mt="4">
                        The opt-out cookie has been removed. This browser can send visits to
                        Google Analytics again as you browse the site.
                    </Text>
                    <Button as="a" href="/no-track" colorScheme="pliny" mt="6">
                        Turn analytics off
                    </Button>
                </>
            )}
        </Page>
    );
}
