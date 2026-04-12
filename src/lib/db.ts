import postgres from 'postgres';

// --- Types ---
export interface Paper {
  arxiv_id: string;
  title: string;
  abstract: string;
  summary_zh: string;
  summary_en: string;
  authors: string;
  url: string;
  published_date: string;
  adjudicator_data?: string;
}

export interface Subscriber {
  email: string;
  language: 'zh' | 'en';
}

// --- Connection Logic (Lazy) ---
let _sql: any = null;
let _schemaInitialized = false;

function getSql() {
  if (!_sql) {
    if (!process.env.DATABASE_URL) {
      // In build environment, DATABASE_URL might be missing. 
      // We return a mock or throw a descriptive error that we catch elsewhere.
      throw new Error('DATABASE_URL is missing. Please check your environment variables.');
    }
    _sql = postgres(process.env.DATABASE_URL, {
      ssl: 'require',
      connect_timeout: 10,
    });
  }
  return _sql;
}

// Initialize database schema (PostgreSQL version)
async function initSchema() {
  if (_schemaInitialized) return;

  try {
    const sql = getSql();
    await sql`
      CREATE TABLE IF NOT EXISTS papers (
        id SERIAL PRIMARY KEY,
        arxiv_id TEXT UNIQUE,
        title TEXT,
        abstract TEXT,
        summary_zh TEXT,
        summary_en TEXT,
        authors TEXT,
        url TEXT,
        published_date TEXT,
        adjudicator_data TEXT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
      );
    `;

    // Ensure the column exists for existing setups, including Supabase
    await sql`ALTER TABLE papers ADD COLUMN IF NOT EXISTS adjudicator_data TEXT;`;

    await sql`
      CREATE TABLE IF NOT EXISTS subscribers (
        id SERIAL PRIMARY KEY,
        email TEXT UNIQUE,
        language TEXT DEFAULT 'zh',
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
      );
    `;
    // Add language column if it doesn't exist (for existing tables)
    await sql`ALTER TABLE subscribers ADD COLUMN IF NOT EXISTS language TEXT DEFAULT 'zh'`;
    _schemaInitialized = true;
    console.log('Database schema initialized.');
  } catch (err) {
    // If it's a connection error during build, we log and continue
    console.error('Database initialization failed:', err);
    throw err;
  }
}

// Helper to ensure connection and schema before any operation
async function ensureDb() {
  try {
    await initSchema();
  } catch (err) {
    // Graceful degradation or error propagation
    console.warn('Database not available at this moment.');
    throw err;
  }
}

// --- Database Operations ---
export const dbOps = {
  savePaper: async (paper: Paper) => {
    await ensureDb();
    const sql = getSql();
    return await sql`
      INSERT INTO papers (arxiv_id, title, abstract, summary_zh, summary_en, authors, url, published_date, adjudicator_data)
      VALUES (${paper.arxiv_id}, ${paper.title}, ${paper.abstract}, ${paper.summary_zh}, ${paper.summary_en}, ${paper.authors}, ${paper.url}, ${paper.published_date}, ${paper.adjudicator_data || null})
      ON CONFLICT (arxiv_id) DO UPDATE SET
        summary_zh = EXCLUDED.summary_zh,
        summary_en = EXCLUDED.summary_en,
        adjudicator_data = EXCLUDED.adjudicator_data,
        created_at = CURRENT_TIMESTAMP
    `;
  },

  getLatestPaper: async (): Promise<Paper | null> => {
    try {
      await ensureDb();
      const sql = getSql();
      const result = await sql`
        SELECT * FROM papers ORDER BY created_at DESC LIMIT 1
      `;
      return (result[0] as unknown as Paper) || null;
    } catch (err) {
      console.error('Error fetching latest paper:', err);
      return null;
    }
  },

  getLatestHighlightPaper: async (): Promise<Paper | null> => {
    try {
      await ensureDb();
      const sql = getSql();
      const result = await sql`
        SELECT * FROM papers WHERE adjudicator_data IS NOT NULL ORDER BY created_at DESC LIMIT 1
      `;
      return (result[0] as unknown as Paper) || null;
    } catch (err) {
      console.error('Error fetching latest highlight paper:', err);
      return null;
    }
  },

  getAllSubscribers: async (): Promise<Subscriber[]> => {
    await ensureDb();
    const sql = getSql();
    const result = await sql`
      SELECT email, COALESCE(language, 'zh') as language FROM subscribers
    `;
    return result as unknown as Subscriber[];
  },

  addSubscriber: async (email: string, language: 'zh' | 'en' = 'zh') => {
    await ensureDb();
    const sql = getSql();
    return await sql`
      INSERT INTO subscribers (email, language) VALUES (${email}, ${language})
      ON CONFLICT (email) DO UPDATE SET language = EXCLUDED.language
    `;
  },

  removeSubscriber: async (email: string) => {
    await ensureDb();
    const sql = getSql();
    return await sql`
      DELETE FROM subscribers WHERE email = ${email}
    `;
  },

  isSubscriberExists: async (email: string): Promise<boolean> => {
    try {
      await ensureDb();
      const sql = getSql();
      const result = await sql`
        SELECT 1 FROM subscribers WHERE email = ${email}
      `;
      return result.length > 0;
    } catch (err) {
      console.error('Error checking subscriber existence:', err);
      return false;
    }
  }
};
