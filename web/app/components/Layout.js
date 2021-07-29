import Head from 'next/head'

export default function Layout({
  children,
  title = "RWC Weather",
}) {
  return (
    <div>
      <Head>
        <title>{title}</title>
      </Head>
      {children}
    </div>
  )
}