import React from 'react';

export const metadata = {
  title: 'Chemical Store Management System',
  description: 'Real UI for chemical inventory management',
};

export default function HomePage() {
  // If the rewrite doesn't kick in for some reason during local dev,
  // we can use a meta refresh to redirect to /app.html
  return (
    <>
      <meta httpEquiv="refresh" content="0; url=/app.html" />
      <div style={{ padding: '2rem', fontFamily: 'sans-serif' }}>
        Redirecting to application...
      </div>
    </>
  );
}
