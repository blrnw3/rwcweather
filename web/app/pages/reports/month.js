import Link from 'next/link'
import Head from 'next/head'


export default function HistoryMonth() {
  return (
    <>
      <Head>
          <title>Monthly History</title>
        </Head>
      <h1>January 2021</h1>
      <h2>
          <Link href="/">
            <a>Back to home</a>
          </Link>
        </h2>
    </>
  )
}
