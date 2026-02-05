import "./globals.css";

export const metadata = {
    title: "KidneyStone AI",
    description: "Provider portal",
};

export default function RootLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <html lang="en">
            <body>{children}</body>
        </html>
    );
}
