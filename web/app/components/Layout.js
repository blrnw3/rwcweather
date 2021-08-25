import Head from 'next/head'

export default function Layout({
  children,
  title = "",
}) {
    let fullTitle = "RWC Weather | " + title;
  return (
    <div>
      <Head>
        <title>{fullTitle}</title>
      </Head>
      {children}
    </div>
  )
}