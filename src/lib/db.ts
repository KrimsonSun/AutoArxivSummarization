import Database from 'better-sqlite3';
import path from 'path';
import fs from 'fs';

const DB_PATH = process.env.DATABASE_URL || 'data/database.sqlite';

// Ensure the data directory exists
const dbDir = path.dirname(path.resolve(process.cwd(), DB_PATH));
if (!fs.existsSync(dbDir)) {
  fs.mkdirSync(dbDir, { recursive: true });
}

const db = new Database(DB_PATH);

// Initialize tables
db.exec(`
  CREATE TABLE IF NOT EXISTS papers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    arxiv_id TEXT UNIQUE,
    title TEXT,
    abstract TEXT,
    summary_zh TEXT,
    summary_en TEXT,
    authors TEXT,
    url TEXT,
    published_date TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS subscribers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );
`);

export default db;

export interface Paper {
  id?: number;
  arxiv_id: string;
  title: string;
  abstract: string;
  summary_zh: string;
  summary_en: string;
  authors: string;
  url: string;
  published_date: string;
  created_at?: string;
}

export interface Subscriber {
  id?: number;
  email: string;
  created_at?: string;
}

export const dbOps = {
  savePaper: (paper: Paper) => {
    const stmt = db.prepare(`
      INSERT OR REPLACE INTO papers (arxiv_id, title, abstract, summary_zh, summary_en, authors, url, published_date)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `);
    return stmt.run(
      paper.arxiv_id,
      paper.title,
      paper.abstract,
      paper.summary_zh,
      paper.summary_en,
      paper.authors,
      paper.url,
      paper.published_date
    );
  },

  getLatestPaper: (): Paper | undefined => {
    return db.prepare('SELECT * FROM papers ORDER BY created_at DESC LIMIT 1').get() as Paper | undefined;
  },

  addSubscriber: (email: string) => {
    const stmt = db.prepare('INSERT OR IGNORE INTO subscribers (email) VALUES (?)');
    return stmt.run(email);
  },

  isSubscriberExists: (email: string): boolean => {
    const stmt = db.prepare('SELECT 1 FROM subscribers WHERE email = ?');
    return !!stmt.get(email);
  },

  removeSubscriber: (email: string) => {
    const stmt = db.prepare('DELETE FROM subscribers WHERE email = ?');
    return stmt.run(email);
  },

  getAllSubscribers: (): Subscriber[] => {
    return db.prepare('SELECT * FROM subscribers').all() as Subscriber[];
  }
};
