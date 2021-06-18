export const fetcher = url => fetch(process.env.NEXT_PUBLIC_API_HOST + url).then(res => res.json());
