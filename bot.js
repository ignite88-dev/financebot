require('dotenv').config();
const TelegramBot = require('node-telegram-bot-api');
const axios = require('axios');
const fs = require('fs').promises;
const moment = require('moment');

// ================= CONFIG =================
const CONFIG = {
    TELEGRAM_TOKEN: process.env.TELEGRAM_TOKEN,
    DEEPSEEK_API_KEY: process.env.DEEPSEEK_API_KEY,
    GROUP_CHAT_ID: process.env.GROUP_CHAT_ID,
    MEMORY_FILE: 'memory.json',
    AUTO_SAVE_INTERVAL: 15000,
    AI_TIMEOUT: 25000,
    MAX_RETRIES: 2,
    DAILY_LIMIT: 20,
    MONTHLY_LIMIT: 1000  // $600 per bulan
};

// ================= BOT =================
const bot = new TelegramBot(CONFIG.TELEGRAM_TOKEN, { 
    polling: {
        interval: 300,
        autoStart: true,
        params: { timeout: 10 }
    }
});

// ================= MEMORY STRUCTURE =================
let memory = {
    wallet: { IDR: 0, USD: 0 },
    dailySpent: { 
        USD: 0, 
        limit: CONFIG.DAILY_LIMIT, 
        date: new Date().toDateString(),
        warnings: []
    },
    monthlySpent: {
        USD: 0,
        limit: CONFIG.MONTHLY_LIMIT,
        month: moment().format('YYYY-MM'),
        categories: {}
    },
    exchangeRate: 15000,
    transactions: [],
    lastSaved: null
};

// ================= LOGGER =================
function log(type, message) {
    const time = moment().format('HH:mm:ss');
    const emoji = { 
        info: 'ℹ️', success: '✅', error: '❌', ai: '🤖', 
        warning: '⚠️', money: '💸', limit: '🚨'
    };
    console.log(`${emoji[type] || '📝'} [${time}] ${message}`);
}

// ================= LOAD MEMORY =================
async function loadMemory() {
    try {
        const data = await fs.readFile(CONFIG.MEMORY_FILE, 'utf8');
        const saved = JSON.parse(data);
        
        const today = new Date().toDateString();
        const currentMonth = moment().format('YYYY-MM');
        
        // Reset daily jika hari baru
        if (saved.dailySpent && saved.dailySpent.date !== today) {
            saved.dailySpent = { 
                USD: 0, 
                limit: CONFIG.DAILY_LIMIT, 
                date: today,
                warnings: []
            };
            log('info', 'Daily limit direset');
        }
        
        // Reset monthly jika bulan baru
        if (saved.monthlySpent && saved.monthlySpent.month !== currentMonth) {
            saved.monthlySpent = {
                USD: 0,
                limit: CONFIG.MONTHLY_LIMIT,
                month: currentMonth,
                categories: {}
            };
            log('info', 'Monthly limit direset');
        }
        
        memory = {
            wallet: saved.wallet || { IDR: 0, USD: 0 },
            dailySpent: saved.dailySpent || { 
                USD: 0, 
                limit: CONFIG.DAILY_LIMIT, 
                date: today,
                warnings: []
            },
            monthlySpent: saved.monthlySpent || {
                USD: 0,
                limit: CONFIG.MONTHLY_LIMIT,
                month: currentMonth,
                categories: {}
            },
            exchangeRate: saved.exchangeRate || 15000,
            transactions: saved.transactions || [],
            lastSaved: null
        };
        
        // Recalculate from transactions
        recalculateFromTransactions();
        
        log('success', `Memory loaded: ${memory.transactions.length} transaksi`);
        return true;
        
    } catch (error) {
        if (error.code === 'ENOENT') {
            log('info', 'Memory baru dibuat');
            await saveMemory();
            return true;
        }
        log('error', `Gagal load: ${error.message}`);
        return false;
    }
}

// ================= RECALCULATE =================
function recalculateFromTransactions() {
    log('info', 'Menghitung ulang dari transaksi...');
    
    const calculatedWallet = { IDR: 0, USD: 0 };
    const today = new Date().toDateString();
    const currentMonth = moment().format('YYYY-MM');
    let dailySpent = 0;
    let monthlySpent = 0;
    const monthlyCategories = {};
    
    memory.transactions.forEach(txn => {
        if (!txn.canceled) {
            if (txn.type === 'income') {
                calculatedWallet[txn.currency] += txn.amount;
            } else if (txn.type === 'expense') {
                calculatedWallet[txn.currency] -= txn.amount;
                
                const txnDate = new Date(txn.time).toDateString();
                const txnMonth = moment(txn.time).format('YYYY-MM');
                
                if (txn.currency === 'USD') {
                    if (txnDate === today && txn.countsToDailyLimit) {
                        dailySpent += txn.amount;
                    }
                    if (txnMonth === currentMonth) {
                        monthlySpent += txn.amount;
                        
                        // Add to category
                        const category = txn.category || 'other';
                        monthlyCategories[category] = (monthlyCategories[category] || 0) + txn.amount;
                    }
                }
            } else if (txn.type === 'convert') {
                calculatedWallet[txn.currency] -= txn.amount;
                calculatedWallet[txn.targetCurrency] += txn.targetAmount;
            }
        }
    });
    
    // Check for discrepancies
    const idrDiff = Math.abs(calculatedWallet.IDR - memory.wallet.IDR);
    const usdDiff = Math.abs(calculatedWallet.USD - memory.wallet.USD);
    
    if (idrDiff > 1 || usdDiff > 0.01) {
        log('warning', `Perbedaan ditemukan! Memperbaiki...`);
        memory.wallet = calculatedWallet;
        memory.dailySpent.USD = dailySpent;
        memory.monthlySpent.USD = monthlySpent;
        memory.monthlySpent.categories = monthlyCategories;
    }
    
    // Clean up old transactions
    if (memory.transactions.length > 300) {
        const removed = memory.transactions.splice(0, memory.transactions.length - 300);
        log('info', `Dihapus ${removed.length} transaksi lama`);
    }
    
    log('success', 'Rekalkulasi selesai');
}

// ================= SAVE MEMORY =================
async function saveMemory() {
    try {
        memory.lastSaved = new Date().toISOString();
        await fs.writeFile(CONFIG.MEMORY_FILE, JSON.stringify(memory, null, 2));
        return true;
    } catch (error) {
        log('error', `Gagal save: ${error.message}`);
        return false;
    }
}

// ================= ENHANCED AI HANDLER =================
async function askAI(userMessage, userName) {
    try {
        const today = new Date().toDateString();
        const todayTxns = memory.transactions.filter(t => 
            !t.canceled && new Date(t.time).toDateString() === today
        );
        
        // Daily expenses with daily limit
        const dailyUSD = todayTxns
            .filter(t => t.currency === 'USD' && t.type === 'expense' && t.countsToDailyLimit)
            .reduce((sum, t) => sum + t.amount, 0);
        
        // Monthly expenses
        const currentMonth = moment().format('YYYY-MM');
        const monthlyTxns = memory.transactions.filter(t => 
            !t.canceled && moment(t.time).format('YYYY-MM') === currentMonth &&
            t.currency === 'USD' && t.type === 'expense'
        );
        
        const monthlyUSD = monthlyTxns.reduce((sum, t) => sum + t.amount, 0);
        
        const dailyRemaining = Math.max(0, CONFIG.DAILY_LIMIT - dailyUSD);
        const monthlyRemaining = Math.max(0, CONFIG.MONTHLY_LIMIT - monthlyUSD);
        
        // Calculate warnings
        const dailyPercent = (dailyUSD / CONFIG.DAILY_LIMIT) * 100;
        const monthlyPercent = (monthlyUSD / CONFIG.MONTHLY_LIMIT) * 100;
        
        let dailyWarning = '';
        if (dailyPercent >= 80 && dailyPercent < 100) {
            dailyWarning = `⚠️ *PERINGATAN HARIAN:* Sudah ${dailyPercent.toFixed(0)}% dari limit!`;
        } else if (dailyPercent >= 100) {
            dailyWarning = `🚨 *BAHAYA HARIAN:* Limit harian terlampaui ${dailyPercent.toFixed(0)}%!`;
        }
        
        let monthlyWarning = '';
        if (monthlyPercent >= 80 && monthlyPercent < 100) {
            monthlyWarning = `⚠️ *PERINGATAN BULANAN:* Sudah ${monthlyPercent.toFixed(0)}% dari limit bulanan!`;
        } else if (monthlyPercent >= 100) {
            monthlyWarning = `🚨 *BAHAYA BULANAN:* Limit bulanan terlampaui ${monthlyPercent.toFixed(0)}%!`;
        }
        
        const prompt = `
# FINANCE BOT - HARIAN vs BULANAN

## STATUS SAAT INI:
- Saldo: IDR ${memory.wallet.IDR.toLocaleString('id-ID')} | USD ${memory.wallet.USD.toFixed(2)}
- Rate: 1 USD = Rp ${memory.exchangeRate.toLocaleString('id-ID')}

## LIMIT HARIAN ($${CONFIG.DAILY_LIMIT}/hari):
- Terpakai: $${dailyUSD.toFixed(2)} (${dailyPercent.toFixed(0)}%)
- Tersisa: $${dailyRemaining.toFixed(2)}
${dailyWarning ? '- ' + dailyWarning : ''}

## LIMIT BULANAN ($${CONFIG.MONTHLY_LIMIT}/bulan):
- Terpakai: $${monthlyUSD.toFixed(2)} (${monthlyPercent.toFixed(0)}%)
- Tersisa: $${monthlyRemaining.toFixed(2)}
${monthlyWarning ? '- ' + monthlyWarning : ''}

## USER: "${userMessage}" - oleh ${userName}

## ATURAN PENTING:
1. **HARIAN**: USD expenses dengan countsToDailyLimit=true (makan, jajan, transport)
   - BISA melebihi limit, tapi KASIH PERINGATAN KERAS!
   - Jika >80%: "⚠️ PERINGATAN: Hampir mencapai limit harian!"
   - Jika >100%: "🚨 BAHAYA: Melebihi limit harian!"

2. **BULANAN**: Semua USD expenses bulan ini
   - BISA melebihi limit, tapi KASIH PERINGATAN KERAS!
   - Jika >80%: "⚠️ PERINGATAN: Hampir mencapai limit bulanan!"
   - Jika >100%: "🚨 BAHAYA: Melebihi limit bulanan!"

3. **KATEGORI HARIAN** (countsToDailyLimit=true):
   - food, transport, shopping, entertainment, other

4. **KATEGORI BULANAN** (countsToDailyLimit=false):
   - bills, subscription, rent, health, education

5. **IDR expenses**: Tidak ada limit harian/bulanan

## RESPONSE FORMAT (JSON ONLY):
{
  "action": "income|expense|convert|cancel|rate|info",
  "amount": number,
  "currency": "IDR|USD",
  "targetCurrency": "IDR|USD",
  "targetAmount": number,
  "rate": number,
  "category": "food|transport|shopping|entertainment|bills|subscription|rent|health|education|other",
  "description": "string",
  "countsToDailyLimit": boolean,
  "error": null,
  "message": "string response dengan PERINGATAN jika perlu",
  "requires_confirm": boolean,
  "warning_level": "none|warning|danger",
  "warning_message": "string"
}

## CONTOH DENGAN PERINGATAN:

User: "jajan 15 dollar"
{
  "action": "expense",
  "amount": 15,
  "currency": "USD",
  "category": "food",
  "description": "Jajan",
  "countsToDailyLimit": true,
  "message": "🍔 Catat jajan $15",
  "requires_confirm": false,
  "warning_level": "warning",
  "warning_message": "⚠️ PERINGATAN: Pengeluaran harian akan menjadi $${(dailyUSD + 15).toFixed(2)}/${CONFIG.DAILY_LIMIT} (${((dailyUSD + 15) / CONFIG.DAILY_LIMIT * 100).toFixed(0)}%)!"
}

User: "bayar listrik 50 dollar"
{
  "action": "expense",
  "amount": 50,
  "currency": "USD",
  "category": "bills",
  "description": "Bayar listrik",
  "countsToDailyLimit": false,
  "message": "💡 Catat bayar listrik $50",
  "requires_confirm": false,
  "warning_level": "none",
  "warning_message": ""
}

User: "nongkrong 25 dollar" (jika daily sudah $18)
{
  "action": "expense",
  "amount": 25,
  "currency": "USD",
  "category": "entertainment",
  "description": "Nongkrong",
  "countsToDailyLimit": true,
  "message": "🎉 Catat nongkrong $25",
  "requires_confirm": true,
  "warning_level": "danger",
  "warning_message": "🚨 BAHAYA: Pengeluaran harian akan menjadi $${(dailyUSD + 25).toFixed(2)}/${CONFIG.DAILY_LIMIT} (${((dailyUSD + 25) / CONFIG.DAILY_LIMIT * 100).toFixed(0)}%)! Melebihi limit!"
}

User: "gajian 20 juta"
{
  "action": "income",
  "amount": 20000000,
  "currency": "IDR",
  "description": "Gajian",
  "message": "📥 Gajian Rp 20.000.000 tercatat",
  "requires_confirm": false,
  "warning_level": "none",
  "warning_message": ""
}

User: "cek limit"
{
  "action": "info",
  "message": "📊 *LIMIT STATUS*\\n\\n🍽️ *Harian ($${CONFIG.DAILY_LIMIT}):*\\n├ Terpakai: $${dailyUSD.toFixed(2)} (${dailyPercent.toFixed(0)}%)\\n├ Tersisa: $${dailyRemaining.toFixed(2)}\\n└ Status: ${dailyPercent >= 100 ? '🚨 LEWAT LIMIT' : dailyPercent >= 80 ? '⚠️ HAMPIR LIMIT' : '✅ AMAN'}\\n\\n📅 *Bulanan ($${CONFIG.MONTHLY_LIMIT}):*\\n├ Terpakai: $${monthlyUSD.toFixed(2)} (${monthlyPercent.toFixed(0)}%)\\n├ Tersisa: $${monthlyRemaining.toFixed(2)}\\n└ Status: ${monthlyPercent >= 100 ? '🚨 LEWAT LIMIT' : monthlyPercent >= 80 ? '⚠️ HAMPIR LIMIT' : '✅ AMAN'}",
  "requires_confirm": false,
  "warning_level": "none"
}

## CATATAN:
- countsToDailyLimit=true hanya untuk pengeluaran harian (makan, jajan, transport)
- bills, subscription, rent TIDAK masuk daily limit
- BISA melebihi limit, tapi HARUS kasih peringatan keras!
- Return JSON only.`;

        const response = await axios.post(
            'https://api.deepseek.com/chat/completions',
            {
                model: 'deepseek-chat',
                messages: [
                    {
                        role: 'system',
                        content: `Kamu adalah bot keuangan dengan sistem limit HARIAN dan BULANAN. 
                        USD expenses dengan countsToDailyLimit=true (food, transport, shopping, entertainment) akan mengurangi limit harian.
                        USD expenses dengan countsToDailyLimit=false (bills, subscription, rent, health) hanya mengurangi limit bulanan.
                        IDR expenses tidak ada limit.
                        BISA melebihi limit, tapi KASIH PERINGATAN KERAS!
                        Jika >80% limit: "⚠️ PERINGATAN"
                        Jika >100% limit: "🚨 BAHAYA"
                        Return HANYA JSON dengan format di atas.`
                    },
                    {
                        role: 'user',
                        content: prompt
                    }
                ],
                temperature: 0.1,
                max_tokens: 1500,
                response_format: { type: "json_object" }
            },
            {
                headers: {
                    'Authorization': `Bearer ${CONFIG.DEEPSEEK_API_KEY}`,
                    'Content-Type': 'application/json'
                },
                timeout: CONFIG.AI_TIMEOUT
            }
        );

        const aiData = JSON.parse(response.data.choices[0].message.content);
        log('ai', `AI: ${aiData.action} - ${aiData.warning_level || 'no warning'}`);
        return aiData;

    } catch (error) {
        log('error', `AI error: ${error.message}`);
        return {
            action: "error",
            message: "🤖 AI sedang gangguan. Coba lagi!",
            requires_confirm: false,
            warning_level: "none",
            error: true
        };
    }
}

// ================= EXECUTE ACTION WITH WARNINGS =================
async function executeAction(aiData, userName, userId, chatId = null) {
    const time = new Date().toISOString();
    const txnId = `txn_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`;
    
    try {
        if (aiData.error) {
            return { 
                success: false, 
                message: `❌ ${aiData.error}`,
                warning: null
            };
        }
        
        const action = aiData.action;
        
        // INFO ACTION
        if (action === 'info') {
            return { 
                success: true, 
                message: aiData.message,
                infoOnly: true,
                warning: null
            };
        }
        
        // CANCEL ACTION
        if (action === 'cancel') {
            const userTxns = memory.transactions
                .filter(t => t.userId === userId && !t.canceled)
                .sort((a, b) => new Date(b.time) - new Date(a.time));
            
            if (userTxns.length === 0) {
                return { 
                    success: false, 
                    message: "❌ Tidak ada transaksi untuk dibatalkan",
                    warning: null
                };
            }
            
            const lastTxn = userTxns[0];
            
            // Reverse transaction
            if (lastTxn.type === 'income') {
                memory.wallet[lastTxn.currency] -= lastTxn.amount;
            } else if (lastTxn.type === 'expense') {
                memory.wallet[lastTxn.currency] += lastTxn.amount;
                
                // Update limits if USD
                if (lastTxn.currency === 'USD') {
                    const txnDate = new Date(lastTxn.time).toDateString();
                    const txnMonth = moment(lastTxn.time).format('YYYY-MM');
                    const today = new Date().toDateString();
                    const currentMonth = moment().format('YYYY-MM');
                    
                    if (txnDate === today && lastTxn.countsToDailyLimit) {
                        memory.dailySpent.USD = Math.max(0, memory.dailySpent.USD - lastTxn.amount);
                    }
                    if (txnMonth === currentMonth) {
                        memory.monthlySpent.USD = Math.max(0, memory.monthlySpent.USD - lastTxn.amount);
                        
                        // Remove from category
                        const category = lastTxn.category || 'other';
                        if (memory.monthlySpent.categories[category]) {
                            memory.monthlySpent.categories[category] -= lastTxn.amount;
                            if (memory.monthlySpent.categories[category] <= 0) {
                                delete memory.monthlySpent.categories[category];
                            }
                        }
                    }
                }
            } else if (lastTxn.type === 'convert') {
                memory.wallet[lastTxn.currency] += lastTxn.amount;
                memory.wallet[lastTxn.targetCurrency] -= lastTxn.targetAmount;
            }
            
            lastTxn.canceled = true;
            lastTxn.canceledAt = time;
            lastTxn.canceledBy = userName;
            
            await saveMemory();
            return { 
                success: true, 
                message: aiData.message,
                warning: null
            };
        }
        
        // RATE ACTION
        if (action === 'rate') {
            if (aiData.rate && aiData.rate > 0) {
                const oldRate = memory.exchangeRate;
                memory.exchangeRate = aiData.rate;
                await saveMemory();
                return { 
                    success: true, 
                    message: `💱 Rate diperbarui: ${oldRate.toLocaleString('id-ID')} → ${aiData.rate.toLocaleString('id-ID')}`,
                    warning: null
                };
            }
            return { 
                success: false, 
                message: "❌ Rate tidak valid",
                warning: null
            };
        }
        
        // INCOME ACTION
        if (action === 'income') {
            const amount = aiData.amount;
            const currency = aiData.currency || 'IDR';
            
            if (!amount || amount <= 0) {
                return { 
                    success: false, 
                    message: "❌ Jumlah tidak valid",
                    warning: null
                };
            }
            
            // Add to wallet
            memory.wallet[currency] += amount;
            
            // Add transaction
            memory.transactions.push({
                id: txnId,
                time: time,
                user: userName,
                userId: userId,
                type: 'income',
                amount: amount,
                currency: currency,
                description: aiData.description || "Pemasukan",
                category: aiData.category || 'income',
                canceled: false
            });
            
            await saveMemory();
            return { 
                success: true, 
                message: aiData.message,
                warning: aiData.warning_message || null
            };
        }
        
        // EXPENSE ACTION
        if (action === 'expense') {
            const amount = aiData.amount;
            const currency = aiData.currency || 'IDR';
            const countsToDailyLimit = aiData.countsToDailyLimit || false;
            const category = aiData.category || 'other';
            
            if (!amount || amount <= 0) {
                return { 
                    success: false, 
                    message: "❌ Jumlah tidak valid",
                    warning: null
                };
            }
            
            // Check balance
            if (amount > memory.wallet[currency]) {
                const needed = currency === 'USD' ? 
                    `$${amount.toFixed(2)}` : 
                    `Rp ${amount.toLocaleString('id-ID')}`;
                const current = currency === 'USD' ?
                    `$${memory.wallet[currency].toFixed(2)}` :
                    `Rp ${memory.wallet[currency].toLocaleString('id-ID')}`;
                    
                return { 
                    success: false, 
                    message: `❌ Saldo ${currency} tidak cukup!\nDibutuhkan: ${needed}\nSaldo: ${current}`,
                    warning: null
                };
            }
            
            // Check limits for USD expenses
            if (currency === 'USD') {
                const today = new Date().toDateString();
                const currentMonth = moment().format('YYYY-MM');
                
                if (countsToDailyLimit) {
                    const newDaily = memory.dailySpent.USD + amount;
                    const dailyPercent = (newDaily / CONFIG.DAILY_LIMIT) * 100;
                    
                    // Update daily limit (ALLOW EXCEEDING WITH WARNING)
                    memory.dailySpent.USD = newDaily;
                    
                    // Add warning if needed
                    if (dailyPercent >= 80 && !memory.dailySpent.warnings.includes('80_percent')) {
                        memory.dailySpent.warnings.push('80_percent');
                    }
                    if (dailyPercent >= 100 && !memory.dailySpent.warnings.includes('100_percent')) {
                        memory.dailySpent.warnings.push('100_percent');
                    }
                }
                
                // Update monthly limit (ALWAYS for USD expenses)
                const newMonthly = memory.monthlySpent.USD + amount;
                memory.monthlySpent.USD = newMonthly;
                
                // Update category spending
                memory.monthlySpent.categories[category] = 
                    (memory.monthlySpent.categories[category] || 0) + amount;
            }
            
            // Deduct from wallet
            memory.wallet[currency] -= amount;
            
            // Add transaction
            memory.transactions.push({
                id: txnId,
                time: time,
                user: userName,
                userId: userId,
                type: 'expense',
                amount: amount,
                currency: currency,
                description: aiData.description || "Pengeluaran",
                category: category,
                countsToDailyLimit: countsToDailyLimit,
                canceled: false
            });
            
            await saveMemory();
            
            // Add warning to response if provided by AI
            let fullMessage = aiData.message;
            if (aiData.warning_message) {
                fullMessage += `\n\n${aiData.warning_message}`;
            }
            
            return { 
                success: true, 
                message: fullMessage,
                warning: aiData.warning_message || null,
                warning_level: aiData.warning_level || 'none'
            };
        }
        
        // CONVERT ACTION
        if (action === 'convert') {
            const amount = aiData.amount;
            const currency = aiData.currency || 'USD';
            const targetCurrency = aiData.targetCurrency || 'IDR';
            const rate = aiData.rate || memory.exchangeRate;
            const targetAmount = aiData.targetAmount || (amount * rate);
            
            if (!amount || amount <= 0) {
                return { 
                    success: false, 
                    message: "❌ Jumlah tidak valid",
                    warning: null
                };
            }
            
            // Check balance
            if (amount > memory.wallet[currency]) {
                return { 
                    success: false, 
                    message: `❌ Saldo ${currency} tidak cukup untuk konversi!`,
                    warning: null
                };
            }
            
            // Update wallet
            memory.wallet[currency] -= amount;
            memory.wallet[targetCurrency] += targetAmount;
            
            // Update rate if provided
            if (aiData.rate && aiData.rate > 0) {
                memory.exchangeRate = aiData.rate;
            }
            
            // Add transaction
            memory.transactions.push({
                id: txnId,
                time: time,
                user: userName,
                userId: userId,
                type: 'convert',
                amount: amount,
                currency: currency,
                targetCurrency: targetCurrency,
                targetAmount: targetAmount,
                rate: rate,
                description: aiData.description || `Konversi ${currency} ke ${targetCurrency}`,
                category: 'convert',
                canceled: false
            });
            
            await saveMemory();
            return { 
                success: true, 
                message: aiData.message,
                warning: aiData.warning_message || null
            };
        }
        
        return { 
            success: false, 
            message: "❌ Action tidak dikenali",
            warning: null
        };
        
    } catch (error) {
        log('error', `Execute error: ${error.message}`);
        return { 
            success: false, 
            message: `❌ Error sistem: ${error.message}`,
            warning: null
        };
    }
}

// ================= KEYBOARD =================
const keyboard = {
    reply_markup: {
        keyboard: [
            ['💰 Saldo', '📊 Harian', '📈 Bulanan'],
            ['🚨 Limits', '🔄 Koreksi', '💱 Rate'],
            ['📋 Kategori', '❓ Bantuan']
        ],
        resize_keyboard: true
    }
};

// ================= HANDLERS =================
async function handleSaldo(chatId) {
    const today = new Date().toDateString();
    const currentMonth = moment().format('YYYY-MM');
    
    const todayTxns = memory.transactions.filter(t => 
        !t.canceled && new Date(t.time).toDateString() === today
    );
    
    const dailyUSD = todayTxns
        .filter(t => t.currency === 'USD' && t.type === 'expense' && t.countsToDailyLimit)
        .reduce((sum, t) => sum + t.amount, 0);
    
    const monthlyTxns = memory.transactions.filter(t => 
        !t.canceled && moment(t.time).format('YYYY-MM') === currentMonth &&
        t.currency === 'USD' && t.type === 'expense'
    );
    
    const monthlyUSD = monthlyTxns.reduce((sum, t) => sum + t.amount, 0);
    
    const dailyRemaining = Math.max(0, CONFIG.DAILY_LIMIT - dailyUSD);
    const monthlyRemaining = Math.max(0, CONFIG.MONTHLY_LIMIT - monthlyUSD);
    
    const dailyPercent = (dailyUSD / CONFIG.DAILY_LIMIT) * 100;
    const monthlyPercent = (monthlyUSD / CONFIG.MONTHLY_LIMIT) * 100;
    
    // Progress bars
    let dailyBar = '';
    let monthlyBar = '';
    for (let i = 0; i < 10; i++) {
        dailyBar += i < Math.floor(dailyPercent / 10) ? 
            (i < 8 ? '🟢' : '🟡') : '⚪';
        monthlyBar += i < Math.floor(monthlyPercent / 10) ? 
            (i < 8 ? '🟢' : '🟡') : '⚪';
    }
    
    const totalWorth = memory.wallet.IDR + (memory.wallet.USD * memory.exchangeRate);
    
    const msg = `
💳 *SALDO & LIMIT*

💰 *SALDO:*
├ IDR: Rp ${memory.wallet.IDR.toLocaleString('id-ID')}
├ USD: $${memory.wallet.USD.toFixed(2)}
└ *TOTAL:* Rp ${totalWorth.toLocaleString('id-ID')}

💱 *RATE:* 1 USD = Rp ${memory.exchangeRate.toLocaleString('id-ID')}

🍽️ *LIMIT HARIAN ($${CONFIG.DAILY_LIMIT}):*
${dailyBar}
├ Terpakai: $${dailyUSD.toFixed(2)} (${dailyPercent.toFixed(0)}%)
├ Tersisa: $${dailyRemaining.toFixed(2)}
└ Status: ${dailyPercent >= 100 ? '🚨 LEWAT LIMIT!' : dailyPercent >= 80 ? '⚠️ HAMPIR LIMIT' : '✅ AMAN'}

📅 *LIMIT BULANAN ($${CONFIG.MONTHLY_LIMIT}):*
${monthlyBar}
├ Terpakai: $${monthlyUSD.toFixed(2)} (${monthlyPercent.toFixed(0)}%)
├ Tersisa: $${monthlyRemaining.toFixed(2)}
└ Status: ${monthlyPercent >= 100 ? '🚨 LEWAT LIMIT!' : monthlyPercent >= 80 ? '⚠️ HAMPIR LIMIT' : '✅ AMAN'}

💸 *TRANSAKSI:*
├ Total: ${memory.transactions.filter(t => !t.canceled).length}
├ Harian: ${todayTxns.length}
└ Bulanan: ${monthlyTxns.length}
`;
    
    await bot.sendMessage(chatId, msg, { 
        parse_mode: 'Markdown',
        reply_markup: keyboard.reply_markup 
    });
}

async function handleDaily(chatId) {
    const today = new Date().toDateString();
    const todayTxns = memory.transactions
        .filter(t => !t.canceled && new Date(t.time).toDateString() === today)
        .sort((a, b) => new Date(b.time) - new Date(a.time));
    
    // Calculate daily USD expenses with daily limit
    const dailyUSD = todayTxns
        .filter(t => t.currency === 'USD' && t.type === 'expense' && t.countsToDailyLimit)
        .reduce((sum, t) => sum + t.amount, 0);
    
    const dailyPercent = (dailyUSD / CONFIG.DAILY_LIMIT) * 100;
    
    if (todayTxns.length === 0) {
        await bot.sendMessage(chatId, 
            '📊 *HARI INI*\n\nBelum ada transaksi.',
            { parse_mode: 'Markdown', reply_markup: keyboard.reply_markup }
        );
        return;
    }
    
    let msg = `📊 *TRANSAKSI HARI INI*\n`;
    msg += `Limit: $${dailyUSD.toFixed(2)}/${CONFIG.DAILY_LIMIT} (${dailyPercent.toFixed(0)}%)\n`;
    msg += `${dailyPercent >= 100 ? '🚨 LEWAT LIMIT!' : dailyPercent >= 80 ? '⚠️ HAMPIR LIMIT' : '✅ MASIH AMAN'}\n`;
    msg += `━━━━━━━━━━━━━━━━━━━━\n\n`;
    
    todayTxns.slice(0, 15).forEach((t) => {
        const emoji = t.type === 'income' ? '📥' : t.type === 'expense' ? '📤' : '💱';
        const amount = t.currency === 'USD' ? 
            `$${t.amount.toFixed(2)}` : 
            `Rp ${t.amount.toLocaleString('id-ID')}`;
        
        let line = `${emoji} *${t.description}*\n   ${amount}`;
        
        if (t.type === 'convert') {
            const targetAmount = t.targetCurrency === 'USD' ?
                `$${t.targetAmount.toFixed(2)}` :
                `Rp ${t.targetAmount.toLocaleString('id-ID')}`;
            line += ` → ${targetAmount}`;
        }
        
        if (t.type === 'expense' && t.currency === 'USD') {
            line += ` ${t.countsToDailyLimit ? '📅' : '📆'}`;
        }
        
        line += `\n   👤 ${t.user} • 🕐 ${moment(t.time).format('HH:mm')}\n\n`;
        msg += line;
    });
    
    if (todayTxns.length > 15) {
        msg += `_...dan ${todayTxns.length - 15} lainnya_`;
    }
    
    await bot.sendMessage(chatId, msg, {
        parse_mode: 'Markdown',
        reply_markup: keyboard.reply_markup
    });
}

async function handleMonthly(chatId) {
    const currentMonth = moment().format('YYYY-MM');
    const monthTxns = memory.transactions
        .filter(t => !t.canceled && moment(t.time).format('YYYY-MM') === currentMonth)
        .sort((a, b) => new Date(b.time) - new Date(a.time));
    
    const monthlyUSD = monthTxns
        .filter(t => t.currency === 'USD' && t.type === 'expense')
        .reduce((sum, t) => sum + t.amount, 0);
    
    const monthlyPercent = (monthlyUSD / CONFIG.MONTHLY_LIMIT) * 100;
    
    if (monthTxns.length === 0) {
        await bot.sendMessage(chatId, 
            `📅 *BULAN ${moment().format('MMMM YYYY')}*\n\nBelum ada transaksi.`,
            { parse_mode: 'Markdown', reply_markup: keyboard.reply_markup }
        );
        return;
    }
    
    // Calculate by category
    const categories = {};
    monthTxns
        .filter(t => t.type === 'expense' && t.currency === 'USD')
        .forEach(t => {
            const cat = t.category || 'other';
            categories[cat] = (categories[cat] || 0) + t.amount;
        });
    
    const topCategories = Object.entries(categories)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5);
    
    let msg = `📅 *BULAN ${moment().format('MMMM YYYY')}*\n`;
    msg += `Limit: $${monthlyUSD.toFixed(2)}/${CONFIG.MONTHLY_LIMIT} (${monthlyPercent.toFixed(0)}%)\n`;
    msg += `${monthlyPercent >= 100 ? '🚨 LEWAT LIMIT!' : monthlyPercent >= 80 ? '⚠️ HAMPIR LIMIT' : '✅ MASIH AMAN'}\n`;
    msg += `━━━━━━━━━━━━━━━━━━━━\n\n`;
    
    msg += `🏷️ *TOP KATEGORI:*\n`;
    if (topCategories.length > 0) {
        topCategories.forEach(([cat, amt]) => {
            const percent = (amt / monthlyUSD) * 100;
            msg += `├ ${cat}: $${amt.toFixed(2)} (${percent.toFixed(1)}%)\n`;
        });
    } else {
        msg += `├ Belum ada pengeluaran USD\n`;
    }
    
    msg += `\n📝 *5 TRANSAKSI TERAKHIR:*\n`;
    monthTxns.slice(0, 5).forEach((t) => {
        const amount = t.currency === 'USD' ? 
            `$${t.amount.toFixed(2)}` : 
            `Rp ${t.amount.toLocaleString('id-ID')}`;
        const date = moment(t.time).format('DD/MM');
        msg += `├ ${t.description}: ${amount} (${date})\n`;
    });
    
    const dailyExpenses = monthTxns
        .filter(t => t.type === 'expense' && t.currency === 'USD' && t.countsToDailyLimit)
        .reduce((sum, t) => sum + t.amount, 0);
    
    const billsExpenses = monthTxns
        .filter(t => t.type === 'expense' && t.currency === 'USD' && !t.countsToDailyLimit)
        .reduce((sum, t) => sum + t.amount, 0);
    
    msg += `\n💸 *RINCIAN:*\n`;
    msg += `├ Harian: $${dailyExpenses.toFixed(2)}\n`;
    msg += `├ Tagihan: $${billsExpenses.toFixed(2)}\n`;
    msg += `└ Total USD: $${monthlyUSD.toFixed(2)}\n`;
    
    await bot.sendMessage(chatId, msg, {
        parse_mode: 'Markdown',
        reply_markup: keyboard.reply_markup
    });
}

async function handleLimits(chatId) {
    const today = new Date().toDateString();
    const currentMonth = moment().format('YYYY-MM');
    
    const dailyUSD = memory.dailySpent.USD;
    const monthlyUSD = memory.monthlySpent.USD;
    
    const dailyPercent = (dailyUSD / CONFIG.DAILY_LIMIT) * 100;
    const monthlyPercent = (monthlyUSD / CONFIG.MONTHLY_LIMIT) * 100;
    
    const dailyRemaining = Math.max(0, CONFIG.DAILY_LIMIT - dailyUSD);
    const monthlyRemaining = Math.max(0, CONFIG.MONTHLY_LIMIT - monthlyUSD);
    
    // Category breakdown
    const categories = Object.entries(memory.monthlySpent.categories)
        .sort((a, b) => b[1] - a[1]);
    
    let msg = `🚨 *STATUS LIMIT*\n━━━━━━━━━━━━━━━━━━━━\n\n`;
    
    msg += `🍽️ *LIMIT HARIAN:* $${CONFIG.DAILY_LIMIT}\n`;
    msg += `├ Terpakai: $${dailyUSD.toFixed(2)} (${dailyPercent.toFixed(0)}%)\n`;
    msg += `├ Tersisa: $${dailyRemaining.toFixed(2)}\n`;
    msg += `└ Status: ${dailyPercent >= 100 ? '🚨 LEWAT LIMIT!' : dailyPercent >= 80 ? '⚠️ HAMPIR LIMIT' : '✅ AMAN'}\n\n`;
    
    msg += `📅 *LIMIT BULANAN:* $${CONFIG.MONTHLY_LIMIT}\n`;
    msg += `├ Terpakai: $${monthlyUSD.toFixed(2)} (${monthlyPercent.toFixed(0)}%)\n`;
    msg += `├ Tersisa: $${monthlyRemaining.toFixed(2)}\n`;
    msg += `└ Status: ${monthlyPercent >= 100 ? '🚨 LEWAT LIMIT!' : monthlyPercent >= 80 ? '⚠️ HAMPIR LIMIT' : '✅ AMAN'}\n\n`;
    
    if (categories.length > 0) {
        msg += `🏷️ *PENGELUARAN PER KATEGORI (Bulan Ini):*\n`;
        categories.forEach(([cat, amt]) => {
            const percent = (amt / monthlyUSD) * 100;
            msg += `├ ${cat}: $${amt.toFixed(2)} (${percent.toFixed(1)}%)\n`;
        });
    }
    
    // Warnings
    const warnings = [];
    if (dailyPercent >= 100) warnings.push(`🚨 Harian: Melebihi limit ${dailyPercent.toFixed(0)}%`);
    else if (dailyPercent >= 80) warnings.push(`⚠️ Harian: Hampir limit ${dailyPercent.toFixed(0)}%`);
    
    if (monthlyPercent >= 100) warnings.push(`🚨 Bulanan: Melebihi limit ${monthlyPercent.toFixed(0)}%`);
    else if (monthlyPercent >= 80) warnings.push(`⚠️ Bulanan: Hampir limit ${monthlyPercent.toFixed(0)}%`);
    
    if (warnings.length > 0) {
        msg += `\n🔔 *PERINGATAN:*\n`;
        warnings.forEach(w => msg += `${w}\n`);
    }
    
    msg += `\n💡 *SARAN:*\n`;
    if (dailyPercent >= 100) {
        msg += `- Kurangi pengeluaran harian (makan, jajan, transport)\n`;
        msg += `- Prioritaskan kebutuhan pokok saja\n`;
    }
    if (monthlyPercent >= 100) {
        msg += `- Tinjau tagihan bulanan (listrik, internet, dll)\n`;
        msg += `- Pertimbangkan untuk menunda pengeluaran besar\n`;
    }
    
    await bot.sendMessage(chatId, msg, {
        parse_mode: 'Markdown',
        reply_markup: keyboard.reply_markup
    });
}

async function handleCategories(chatId) {
    const categories = {
        'food': '🍔 Makan & Minum',
        'transport': '🚗 Transportasi',
        'shopping': '🛍️ Belanja',
        'entertainment': '🎉 Hiburan',
        'bills': '💡 Tagihan',
        'subscription': '📱 Langganan',
        'rent': '🏠 Sewa',
        'health': '🏥 Kesehatan',
        'education': '📚 Pendidikan',
        'other': '📦 Lainnya'
    };
    
    let msg = `📋 *KATEGORI PENGELUARAN*\n━━━━━━━━━━━━━━━━━━━━\n\n`;
    
    msg += `🍽️ *HARIAN (masuk limit harian):*\n`;
    msg += `├ 🍔 food: Makan, jajan, kopi\n`;
    msg += `├ 🚗 transport: Bensin, parkir, transport\n`;
    msg += `├ 🛍️ shopping: Belanja kecil\n`;
    msg += `└ 🎉 entertainment: Nongkrong, bioskop\n\n`;
    
    msg += `📅 *BULANAN (tidak masuk limit harian):*\n`;
    msg += `├ 💡 bills: Listrik, air, internet\n`;
    msg += `├ 📱 subscription: Netflix, Spotify\n`;
    msg += `├ 🏠 rent: Sewa rumah/kantor\n`;
    msg += `├ 🏥 health: Obat, dokter\n`;
    msg += `├ 📚 education: Kursus, buku\n`;
    msg += `└ 📦 other: Lain-lain\n\n`;
    
    msg += `💡 *CONTOH:*\n`;
    msg += `• "makan 75rb" → kategori: food (harian)\n`;
    msg += `• "bayar listrik 50 dollar" → kategori: bills (bulanan)\n`;
    msg += `• "beli bensin 200rb" → kategori: transport (harian)\n`;
    
    await bot.sendMessage(chatId, msg, {
        parse_mode: 'Markdown',
        reply_markup: keyboard.reply_markup
    });
}

async function handleStart(chatId, userName) {
    const msg = `
🤖 *FINANCE BOT - HARIAN & BULANAN*

Hai *${userName}*! 👋

💰 *SISTEM LIMIT:*
🍽️ *Harian:* $${CONFIG.DAILY_LIMIT}/hari (makan, transport, hiburan)
📅 *Bulanan:* $${CONFIG.MONTHLY_LIMIT}/bulan (semua pengeluaran USD)

💬 *CONTOH:*
• "makan 75rb" → kategori food (harian)
• "jajan 15 dollar" → kategori food (harian)
• "bayar listrik 50 dollar" → kategori bills (bulanan)
• "netflix 10 dollar" → kategori subscription (bulanan)
• "gajian 20 juta" → pemasukan
• "tukar 500 dolar" → konversi

🚨 *PERINGATAN:* Bot akan kasih peringatan keras jika limit hampir/habis!

📱 Gunakan tombol di bawah:
`;
    
    await bot.sendMessage(chatId, msg, { 
        parse_mode: 'Markdown',
        reply_markup: keyboard.reply_markup
    });
}

// ================= LOADING =================
async function showLoading(chatId) {
    try {
        const msg = '🤖 Memproses...';
        const sent = await bot.sendMessage(chatId, msg);
        return sent.message_id;
    } catch {
        return null;
    }
}

async function removeLoading(chatId, messageId) {
    try {
        if (messageId) await bot.deleteMessage(chatId, messageId);
    } catch {}
}

// ================= PENDING CONFIRMATIONS =================
let pendingConfirmations = {};

// ================= MAIN HANDLER =================
bot.on('message', async (msg) => {
    if (!msg.chat || (msg.chat.type !== 'group' && msg.chat.type !== 'supergroup')) {
        return;
    }
    
    if (!msg.text || msg.from.is_bot) return;
    
    const chatId = msg.chat.id;
    const userId = msg.from.id;
    const userName = msg.from.first_name || 'User';
    const text = msg.text.trim();

    log('info', `${userName}: ${text}`);

    try {
        // Handle buttons
        if (text === '💰 Saldo') return await handleSaldo(chatId);
        if (text === '📊 Harian') return await handleDaily(chatId);
        if (text === '📈 Bulanan') return await handleMonthly(chatId);
        if (text === '🚨 Limits') return await handleLimits(chatId);
        if (text === '📋 Kategori') return await handleCategories(chatId);
        if (text === '🔄 Koreksi') {
            const aiData = {
                action: "cancel",
                message: "🔄 Transaksi terakhir dibatalkan",
                requires_confirm: false
            };
            
            const result = await executeAction(aiData, userName, userId, chatId);
            await bot.sendMessage(chatId, result.message, {
                parse_mode: 'Markdown',
                reply_markup: keyboard.reply_markup
            });
            return;
        }
        if (text === '💱 Rate') {
            await bot.sendMessage(chatId, 
                `💱 Rate: 1 USD = Rp ${memory.exchangeRate.toLocaleString('id-ID')}\n\nKetik "rate 17170" untuk update.`,
                { parse_mode: 'Markdown', reply_markup: keyboard.reply_markup }
            );
            return;
        }
        if (text === '❓ Bantuan') return await handleStart(chatId, userName);
        
        // Handle commands
        if (text.startsWith('/')) {
            const cmd = text.split(' ')[0].toLowerCase();
            if (cmd === '/start' || cmd === '/help') return await handleStart(chatId, userName);
            if (cmd === '/saldo') return await handleSaldo(chatId);
            if (cmd === '/daily') return await handleDaily(chatId);
            if (cmd === '/monthly') return await handleMonthly(chatId);
            if (cmd === '/limits') return await handleLimits(chatId);
            if (cmd === '/categories') return await handleCategories(chatId);
        }
        
        if (text.length < 2) return;
        
        // AI Processing
        await bot.sendChatAction(chatId, 'typing');
        const loadingId = await showLoading(chatId);
        
        try {
            const aiData = await askAI(text, userName);
            
            if (aiData.error) {
                await removeLoading(chatId, loadingId);
                await bot.sendMessage(chatId, aiData.message, {
                    parse_mode: 'Markdown',
                    reply_markup: keyboard.reply_markup
                });
                return;
            }
            
            // Handle confirmation
            if (aiData.requires_confirm) {
                await removeLoading(chatId, loadingId);
                
                const confirmId = `confirm_${Date.now()}_${userId}`;
                const confirmKeyboard = {
                    inline_keyboard: [[
                        { text: '✅ Ya, Lanjutkan', callback_data: `${confirmId}_yes` },
                        { text: '❌ Tidak, Batalkan', callback_data: `${confirmId}_no` }
                    ]]
                };
                
                let confirmMsg = `🔄 *KONFIRMASI TRANSAKSI*\n\n${aiData.message}`;
                if (aiData.warning_message) {
                    confirmMsg += `\n\n${aiData.warning_message}`;
                }
                confirmMsg += `\n\n*Lanjutkan?*`;
                
                await bot.sendMessage(chatId, confirmMsg, { 
                    parse_mode: 'Markdown',
                    reply_markup: confirmKeyboard 
                });
                
                pendingConfirmations[confirmId] = {
                    userId: userId,
                    userName: userName,
                    aiData: aiData,
                    timestamp: Date.now()
                };
                
                setTimeout(() => {
                    if (pendingConfirmations[confirmId]) {
                        delete pendingConfirmations[confirmId];
                    }
                }, 60000);
                
                return;
            }
            
            const result = await executeAction(aiData, userName, userId, chatId);
            await removeLoading(chatId, loadingId);
            
            let response = result.message;
            
            if (result.success && !result.infoOnly) {
                // Add status
                const today = new Date().toDateString();
                const currentMonth = moment().format('YYYY-MM');
                
                const dailyUSD = memory.dailySpent.USD;
                const monthlyUSD = memory.monthlySpent.USD;
                
                response += `\n\n━━━━━━━━━━━━━━━━━━━━`;
                response += `\n💰 Saldo: Rp ${memory.wallet.IDR.toLocaleString('id-ID')} | $${memory.wallet.USD.toFixed(2)}`;
                response += `\n🍽️ Harian: $${dailyUSD.toFixed(2)}/${CONFIG.DAILY_LIMIT}`;
                response += `\n📅 Bulanan: $${monthlyUSD.toFixed(2)}/${CONFIG.MONTHLY_LIMIT}`;
            }
            
            await bot.sendMessage(chatId, response, { 
                parse_mode: 'Markdown',
                reply_markup: keyboard.reply_markup
            });
            
            log('success', `Processed: ${aiData.action} (${aiData.warning_level || 'no warning'})`);
            
        } catch (error) {
            await removeLoading(chatId, loadingId);
            throw error;
        }

    } catch (error) {
        log('error', `Handler error: ${error.message}`);
        await bot.sendMessage(chatId, 
            `❌ Error: ${error.message}`,
            { parse_mode: 'Markdown', reply_markup: keyboard.reply_markup }
        );
    }
});

// ================= CALLBACK HANDLER =================
bot.on('callback_query', async (callbackQuery) => {
    const chatId = callbackQuery.message.chat.id;
    const userId = callbackQuery.from.id;
    const data = callbackQuery.data;
    const messageId = callbackQuery.message.message_id;
    
    try {
        await bot.answerCallbackQuery(callbackQuery.id);
        
        if (data.includes('_yes') || data.includes('_no')) {
            const baseId = data.substring(0, data.lastIndexOf('_'));
            const action = data.endsWith('_yes') ? 'confirm' : 'cancel';
            
            const pending = pendingConfirmations[baseId];
            
            if (!pending) {
                await bot.sendMessage(chatId, "❌ Konfirmasi sudah kadaluarsa");
                return;
            }
            
            if (pending.userId !== userId) {
                await bot.sendMessage(chatId, "❌ Hanya user yang meminta konfirmasi yang bisa melanjutkan");
                return;
            }
            
            delete pendingConfirmations[baseId];
            
            if (action === 'cancel') {
                await bot.editMessageText(
                    "❌ Transaksi dibatalkan.",
                    { chat_id: chatId, message_id: messageId, parse_mode: 'Markdown' }
                );
                return;
            }
            
            const result = await executeAction(pending.aiData, pending.userName, userId, chatId);
            
            let response = `✅ *DIKONFIRMASI*\n\n${result.message}`;
            
            if (result.success && !result.infoOnly) {
                const dailyUSD = memory.dailySpent.USD;
                const monthlyUSD = memory.monthlySpent.USD;
                
                response += `\n\n━━━━━━━━━━━━━━━━━━━━`;
                response += `\n💰 Saldo: Rp ${memory.wallet.IDR.toLocaleString('id-ID')} | $${memory.wallet.USD.toFixed(2)}`;
                response += `\n🍽️ Harian: $${dailyUSD.toFixed(2)}/${CONFIG.DAILY_LIMIT}`;
                response += `\n📅 Bulanan: $${monthlyUSD.toFixed(2)}/${CONFIG.MONTHLY_LIMIT}`;
            }
            
            await bot.editMessageText(response, {
                chat_id: chatId,
                message_id: messageId,
                parse_mode: 'Markdown'
            });
        }
        
    } catch (error) {
        log('error', `Callback error: ${error.message}`);
    }
});

// ================= STARTUP =================
async function startBot() {
    try {
        console.log('\n' + '='.repeat(50));
        console.log('🚀 FINANCE BOT - HARIAN & BULANAN');
        console.log('='.repeat(50));
        
        await loadMemory();
        
        const me = await bot.getMe();
        console.log(`🤖 Bot: @${me.username}`);
        console.log(`💰 Saldo: Rp ${memory.wallet.IDR.toLocaleString('id-ID')} | $${memory.wallet.USD.toFixed(2)}`);
        console.log(`💱 Rate: 1 USD = Rp ${memory.exchangeRate.toLocaleString('id-ID')}`);
        console.log(`🍽️ Harian: $${memory.dailySpent.USD.toFixed(2)}/${CONFIG.DAILY_LIMIT}`);
        console.log(`📅 Bulanan: $${memory.monthlySpent.USD.toFixed(2)}/${CONFIG.MONTHLY_LIMIT}`);
        console.log(`📊 Transaksi: ${memory.transactions.filter(t => !t.canceled).length}`);
        
        console.log('\n✅ BOT READY!');
        console.log('='.repeat(50) + '\n');
        
        setInterval(async () => {
            try {
                await saveMemory();
            } catch (error) {
                log('error', `Auto-save failed: ${error.message}`);
            }
        }, CONFIG.AUTO_SAVE_INTERVAL);
        
        setInterval(() => {
            const today = new Date().toDateString();
            const currentMonth = moment().format('YYYY-MM');
            
            if (memory.dailySpent.date !== today) {
                memory.dailySpent = { 
                    USD: 0, 
                    limit: CONFIG.DAILY_LIMIT, 
                    date: today,
                    warnings: []
                };
                saveMemory();
                log('info', 'Daily limit direset');
            }
            
            if (memory.monthlySpent.month !== currentMonth) {
                memory.monthlySpent = {
                    USD: 0,
                    limit: CONFIG.MONTHLY_LIMIT,
                    month: currentMonth,
                    categories: {}
                };
                saveMemory();
                log('info', 'Monthly limit direset');
            }
        }, 60000);
        
        if (CONFIG.GROUP_CHAT_ID) {
            setTimeout(() => {
                const dailyPercent = (memory.dailySpent.USD / CONFIG.DAILY_LIMIT) * 100;
                const monthlyPercent = (memory.monthlySpent.USD / CONFIG.MONTHLY_LIMIT) * 100;
                
                let status = '';
                if (dailyPercent >= 100 || monthlyPercent >= 100) {
                    status = '🚨 ADA LIMIT YANG LEWAT!';
                } else if (dailyPercent >= 80 || monthlyPercent >= 80) {
                    status = '⚠️ HAMPIR LIMIT!';
                } else {
                    status = '✅ SEMUA AMAN';
                }
                
                bot.sendMessage(CONFIG.GROUP_CHAT_ID,
                    `🤖 *BOT LIMIT AKTIF!*\n\n` +
                    `💰 Saldo: Rp ${memory.wallet.IDR.toLocaleString('id-ID')} | $${memory.wallet.USD.toFixed(2)}\n` +
                    `🍽️ Harian: $${memory.dailySpent.USD.toFixed(2)}/${CONFIG.DAILY_LIMIT}\n` +
                    `📅 Bulanan: $${memory.monthlySpent.USD.toFixed(2)}/${CONFIG.MONTHLY_LIMIT}\n` +
                    `📊 Status: ${status}\n\n` +
                    `💬 Contoh: "jajan 15 dollar" atau "bayar listrik 50 dollar"\n` +
                    `🚨 Bot akan kasih peringatan jika limit hampir/habis!`,
                    { 
                        parse_mode: 'Markdown',
                        reply_markup: keyboard.reply_markup 
                    }
                ).catch(() => {});
            }, 2000);
        }
        
    } catch (error) {
        console.error('❌ STARTUP ERROR:', error);
        process.exit(1);
    }
}

// ================= ERROR HANDLERS =================
process.on('uncaughtException', async (error) => {
    log('error', `CRASH: ${error.message}`);
    try {
        await saveMemory();
        console.log('💾 Emergency save successful');
    } catch (e) {
        console.error('❌ Emergency save failed:', e.message);
    }
    setTimeout(() => {
        console.log('💥 RESTARTING...');
        process.exit(1);
    }, 3000);
});

process.on('unhandledRejection', (reason) => {
    log('error', `REJECTION: ${reason}`);
});

process.on('SIGINT', async () => {
    console.log('\n🛑 SHUTDOWN');
    try {
        await saveMemory();
        console.log('💾 Data saved');
    } catch (error) {
        console.error('❌ Save failed:', error.message);
    }
    console.log('👋 GOODBYE');
    process.exit(0);
});

// ================= START =================
startBot();