import fs from 'fs';
import path from 'path';
import React from 'react';

export const metadata = {
  title: 'Chemical Store Management System Dashboard',
  description: 'Real UI for chemical inventory management',
};

export default function HomePage() {
  const filePath = path.join(process.cwd(), 'static', 'index.html');
  let html = '';
  try {
    html = fs.readFileSync(filePath, 'utf8');
  } catch (e) {
    console.error('Failed to read static index.html', e);
    return <div>Failed to load UI.</div>;
  }
  const bodyMatch = html.match(/<body[^>]*>([\s\S]*?)<\/body>/i);
  const body = bodyMatch ? bodyMatch[1] : html;
  return <section dangerouslySetInnerHTML={{ __html: body }} />;
}
