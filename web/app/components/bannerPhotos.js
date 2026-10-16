// Banner photos (Ben's own, EXIF stripped, WebP). Files live in web/app/public/img/banner/.
// HERO_PHOTO sits permanently behind the wordmark (all screen sizes, under a dark gradient).
// SEASONAL_PHOTOS: the set for the current season is shown to the right of the wordmark
// on md+ screens (1 on tablet, 3 on desktop). Empty season list = hero only.
export const HERO_PHOTO = "/img/banner/hero.webp";

// winter Dec-Feb, spring Mar-May, summer Jun-Aug, autumn Sep-Nov
export function seasonOf(month) { // month 0-11
  return ["winter", "winter", "spring", "spring", "spring", "summer", "summer", "summer", "autumn", "autumn", "autumn", "winter"][month];
}

export const SEASONAL_PHOTOS = {
  winter: [
    { src: "/img/banner/winter-7.webp", alt: "Oak over a fog-filled valley, January" },
    { src: "/img/banner/winter-8.webp", alt: "Clouds over the bay, January" },
    { src: "/img/banner/winter-11.webp", alt: "Grey winter sky over the hills, February" },
  ],
  spring: [
    { src: "/img/banner/spring-1.webp", alt: "Low cloud lifting off the ridges, April" },
    { src: "/img/banner/spring-20.webp", alt: "Storm clouds over the hills, April" },
    { src: "/img/banner/spring-23.webp", alt: "Cumulus over a green hilltop, April" },
  ],
  summer: [
    { src: "/img/banner/summer-25.webp", alt: "Clear summer sky over the hills, June" },
    { src: "/img/banner/summer-28.webp", alt: "Broken cloud over summer hills, July" },
    { src: "/img/banner/summer-30.webp", alt: "Cirrus over the ridges, August" },
  ],
  autumn: [
    { src: "/img/banner/autumn-31.webp", alt: "Sunset clouds over the ridge, September" },
    { src: "/img/banner/autumn-34.webp", alt: "Evening sky over the oaks, October" },
    { src: "/img/banner/autumn-37.webp", alt: "Fog over a dry meadow, October" },
  ],
};
