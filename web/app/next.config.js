module.exports = {
    async redirects() {
        return [
            {
                source: "/reports/month",
                destination: "/reports/alltime",
                permanent: true,
            },
        ];
    },
};
