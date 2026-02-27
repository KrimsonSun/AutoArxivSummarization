import { dbOps } from './src/lib/db.js';
import dotenv from 'dotenv';
dotenv.config({ path: '.env.local' });

async function testDB() {
    console.log('Testing Supabase Connection...');
    try {
        await dbOps.addSubscriber('test@example.com');
        console.log('Added test subscriber.');

        const subs = await dbOps.getAllSubscribers();
        console.log('Current Subscribers:', subs);

        console.log('DB Test Successful!');
    } catch (e) {
        console.error('DB Test Failed:', e);
    } finally {
        process.exit();
    }
}

testDB();
