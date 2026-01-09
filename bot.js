require('dotenv').config();
const TelegramBot = require('node-telegram-bot-api');
const axios = require('axios');
const fs = require('fs').promises;
const path = require('path');
const moment = require('moment-timezone');

// ================= CONFIGURATION =================
const CONFIG = {
    TELEGRAM_TOKEN: process.env.TELEGRAM_TOKEN,
    DEEPSEEK_API_KEY: process.env.DEEPSEEK_API_KEY,
    SUPER_ADMIN_IDS: process.env.SUPER_ADMIN_IDS ? 
        process.env.SUPER_ADMIN_IDS.split(',').map(id => parseInt(id.trim())) : [],
    DATA_DIR: 'data',
    GROUPS_FILE: 'groups.json',
    DEFAULT_DAILY_LIMIT: 20,
    DEFAULT_MONTHLY_LIMIT: 1000,
    AUTO_SAVE_INTERVAL: 15000,
    AI_TIMEOUT: 30000,
    MAX_RETRIES: 3,
    TIMEZONE: 'Asia/Jakarta',
    DEFAULT_RATE: 15000
};

// ================= BOT INITIALIZATION =================
const bot = new TelegramBot(CONFIG.TELEGRAM_TOKEN, {
    polling: {
        interval: 300,
        autoStart: true,
        params: { timeout: 10 }
    }
});

// ================= DATA STORAGE =================
let groupsData = {};
let globalConfig = {
    whitelist: [],
    blacklist: [],
    autoApprove: false
};
let pendingConfirmations = {};
let processingMessages = new Set();

// ================= ENHANCED LOGGER =================
function log(type, message, data = null) {
    const time = moment().tz(CONFIG.TIMEZONE).format('HH:mm:ss');
    const emoji = {
        info: 'ℹ️', success: '✅', error: '❌', ai: '🤖',
        warning: '⚠️', money: '💸', limit: '🚨',
        group: '👥', admin: '👑', system: '🔧',
        typing: '⌨️', loading: '⏳', debug: '🐛',
        super: '👑👑', panel: '📱', user: '👤'
    };
    
    console.log(`${emoji[type] || '📝'} [${time}] ${message}`);
    if (data && process.env.DEBUG === 'true') {
        console.log('   📊 Data:', JSON.stringify(data, null, 2).substring(0, 500));
    }
    
    return { time, type, message, data };
}

// ================= DATA MANAGEMENT =================
async function ensureDirectories() {
    const dirs = [CONFIG.DATA_DIR, path.join(CONFIG.DATA_DIR, 'groups')];
    
    for (const dir of dirs) {
        try {
            await fs.mkdir(dir, { recursive: true });
        } catch (error) {
            log('error', `Failed to create directory ${dir}: ${error.message}`);
        }
    }
}

async function loadAllData() {
    try {
        await ensureDirectories();
        
        // Load global config
        const globalConfigPath = path.join(CONFIG.DATA_DIR, 'global.json');
        try {
            const data = await fs.readFile(globalConfigPath, 'utf8');
            globalConfig = JSON.parse(data);
            log('success', 'Global config loaded');
        } catch (error) {
            globalConfig = { whitelist: [], blacklist: [], autoApprove: false };
            await fs.writeFile(globalConfigPath, JSON.stringify(globalConfig, null, 2));
            log('info', 'Created new global config');
        }
        
        // Load groups list
        const groupsPath = path.join(CONFIG.DATA_DIR, CONFIG.GROUPS_FILE);
        try {
            const data = await fs.readFile(groupsPath, 'utf8');
            const savedGroups = JSON.parse(data);
            
            // Load each group's data
            for (const [chatId, groupInfo] of Object.entries(savedGroups)) {
                const groupPath = path.join(CONFIG.DATA_DIR, 'groups', `${chatId}.json`);
                try {
                    const groupData = await fs.readFile(groupPath, 'utf8');
                    groupsData[chatId] = JSON.parse(groupData);
                    log('group', `Group loaded: ${chatId} - ${groupsData[chatId].name}`);
                } catch (error) {
                    groupsData[chatId] = createNewGroupData(chatId, groupInfo);
                    await fs.writeFile(groupPath, JSON.stringify(groupsData[chatId], null, 2));
                    log('group', `Created new data for group: ${chatId}`);
                }
            }
            
            log('success', `Loaded ${Object.keys(groupsData).length} groups`);
        } catch (error) {
            log('info', 'No groups data found, starting fresh');
        }
        
        return true;
    } catch (error) {
        log('error', `Load data failed: ${error.message}`, error.stack);
        return false;
    }
}

async function saveAllData() {
    try {
        await ensureDirectories();
        
        // Save global config
        const globalConfigPath = path.join(CONFIG.DATA_DIR, 'global.json');
        await fs.writeFile(globalConfigPath, JSON.stringify(globalConfig, null, 2));
        
        // Save groups list
        const groupsList = {};
        for (const [chatId, groupData] of Object.entries(groupsData)) {
            groupsList[chatId] = {
                name: groupData.name || `Group ${chatId}`,
                admins: groupData.admins || [],
                created: groupData.created || new Date().toISOString(),
                enabled: groupData.enabled !== false
            };
        }
        
        const groupsPath = path.join(CONFIG.DATA_DIR, CONFIG.GROUPS_FILE);
        await fs.writeFile(groupsPath, JSON.stringify(groupsList, null, 2));
        
        // Save each group's data
        for (const [chatId, groupData] of Object.entries(groupsData)) {
            const groupPath = path.join(CONFIG.DATA_DIR, 'groups', `${chatId}.json`);
            await fs.writeFile(groupPath, JSON.stringify(groupData, null, 2));
        }
        
        log('system', `Saved ${Object.keys(groupsData).length} groups`);
        return true;
    } catch (error) {
        log('error', `Save data failed: ${error.message}`, error.stack);
        return false;
    }
}

function createNewGroupData(chatId, groupInfo = {}) {
    const now = moment().tz(CONFIG.TIMEZONE);
    
    return {
        chatId: chatId.toString(),
        name: groupInfo.name || `Group ${chatId}`,
        enabled: groupInfo.enabled !== false,
        created: new Date().toISOString(),
        admins: groupInfo.admins || [],
        config: {
            dailyLimit: CONFIG.DEFAULT_DAILY_LIMIT,
            monthlyLimit: CONFIG.DEFAULT_MONTHLY_LIMIT,
            timezone: CONFIG.TIMEZONE,
            currency: 'IDR',
            allowAllMembers: true,
            requireAdminForBigTransactions: true,
            bigTransactionThreshold: 1000000,
            notifyOnLimit: true,
            autoResetDaily: true,
            enableChat: true
        },
        memory: {
            wallet: { IDR: 0, USD: 0 },
            dailySpent: {
                USD: 0,
                limit: CONFIG.DEFAULT_DAILY_LIMIT,
                lastReset: now.format('YYYY-MM-DD'),
                resetTime: now.format('HH:mm:ss'),
                warnings: []
            },
            monthlySpent: {
                USD: 0,
                limit: CONFIG.DEFAULT_MONTHLY_LIMIT,
                month: now.format('YYYY-MM'),
                categories: {}
            },
            exchangeRate: CONFIG.DEFAULT_RATE,
            transactions: [],
            statistics: {
                totalTransactions: 0,
                activeUsers: 0,
                lastActivity: new Date().toISOString()
            }
        },
        users: {}
    };
}

// ================= GROUP MANAGEMENT =================
function getGroupData(chatId) {
    const chatIdStr = chatId.toString();
    
    if (!groupsData[chatIdStr]) {
        // Check if group should be auto-created
        const shouldAutoCreate = !globalConfig.blacklist.includes(chatIdStr) && 
                               (globalConfig.autoApprove || globalConfig.whitelist.includes(chatIdStr));
        
        if (shouldAutoCreate) {
            log('group', `Auto-creating new group: ${chatIdStr}`);
            const groupName = `Group ${chatIdStr}`;
            
            groupsData[chatIdStr] = createNewGroupData(chatIdStr, {
                name: groupName,
                enabled: true
            });
            
            // Simpan segera
            saveAllData().catch(error => {
                log('error', `Failed to save new group: ${error.message}`);
            });
            
            return groupsData[chatIdStr];
        }
        
        // Jika tidak boleh auto-create, return null
        return null;
    }
    
    // Pastikan config ada dan lengkap
    if (groupsData[chatIdStr]) {
        if (!groupsData[chatIdStr].config) {
            groupsData[chatIdStr].config = {};
        }
        
        // Set default values untuk config yang belum ada
        const defaults = {
            dailyLimit: CONFIG.DEFAULT_DAILY_LIMIT,
            monthlyLimit: CONFIG.DEFAULT_MONTHLY_LIMIT,
            timezone: CONFIG.TIMEZONE,
            currency: 'IDR',
            allowAllMembers: true,
            requireAdminForBigTransactions: true,
            bigTransactionThreshold: 1000000,
            notifyOnLimit: true,
            autoResetDaily: true,
            enableChat: true
        };
        
        for (const [key, value] of Object.entries(defaults)) {
            if (groupsData[chatIdStr].config[key] === undefined) {
                groupsData[chatIdStr].config[key] = value;
            }
        }
    }
    
    return groupsData[chatIdStr];
}

function ensureGroupConfigComplete(groupData) {
    if (!groupData.config) {
        groupData.config = {};
    }
    
    const defaults = {
        dailyLimit: CONFIG.DEFAULT_DAILY_LIMIT,
        monthlyLimit: CONFIG.DEFAULT_MONTHLY_LIMIT,
        timezone: CONFIG.TIMEZONE,
        currency: 'IDR',
        allowAllMembers: true,
        requireAdminForBigTransactions: true,
        bigTransactionThreshold: 1000000,
        notifyOnLimit: true,
        autoResetDaily: true,
        enableChat: true
    };
    
    for (const [key, value] of Object.entries(defaults)) {
        if (groupData.config[key] === undefined) {
            groupData.config[key] = value;
        }
    }
}

function isGroupAllowed(chatId) {
    const chatIdStr = chatId.toString();
    
    // Check blacklist first
    if (globalConfig.blacklist.includes(chatIdStr)) {
        log('warning', `Group ${chatIdStr} is blacklisted`);
        return false;
    }
    
    // Jika whitelist KOSONG
    if (globalConfig.whitelist.length === 0) {
        if (globalConfig.autoApprove) {
            log('info', `Group ${chatIdStr} allowed via auto-approve`);
            return true;
        } else {
            // Jika whitelist kosong DAN autoApprove OFF
            // Izinkan jika grup sudah ada
            return !!groupsData[chatIdStr];
        }
    }
    
    // Jika ada whitelist, cek apakah ada di whitelist
    if (globalConfig.whitelist.length > 0) {
        return globalConfig.whitelist.includes(chatIdStr);
    }
    
    return true;
}

function isBotEnabledInGroup(chatId) {
    const groupData = getGroupData(chatId);
    if (!groupData) return false;
    return groupData.enabled !== false;
}

function isUserAdmin(chatId, userId) {
    const groupData = getGroupData(chatId);
    if (!groupData) return false;
    
    // Super admin always has access
    if (CONFIG.SUPER_ADMIN_IDS.includes(parseInt(userId))) {
        return true;
    }
    
    // Check group admins
    return groupData.admins && groupData.admins.includes(userId.toString());
}

// ================= KEYBOARD HELPER =================
function getGroupKeyboard(chatId, userId) {
    const isSuperAdmin = CONFIG.SUPER_ADMIN_IDS.includes(parseInt(userId));
    const isGroupAdmin = isUserAdmin(chatId, userId);
    const groupData = getGroupData(chatId);
    
    let keyboard = [];
    
    // ================= USER BIASA =================
    if (!isSuperAdmin && !isGroupAdmin) {
        keyboard = [
            [{ text: '💰 Saldo' }, { text: '📊 Harian' }, { text: '📅 Bulanan' }],
            [{ text: '🔄 Koreksi' }, { text: '💱 Rate' }, { text: '📈 Stats' }],
            [{ text: '❓ Bantuan' }]
        ];
    }
    
    // ================= ADMIN GRUP =================
    else if (!isSuperAdmin && isGroupAdmin) {
        keyboard = [
            [{ text: '💰 Saldo' }, { text: '📊 Harian' }, { text: '📅 Bulanan' }],
            [{ text: '🔄 Koreksi' }, { text: '💱 Rate' }, { text: '📈 Stats' }],
            [{ text: '⚙️ Config' }, { text: '👥 Users' }, { text: '📋 Transaksi' }],
            [{ text: '👑 Admin Panel' }]
        ];
    }
    
    // ================= SUPER ADMIN =================
    else if (isSuperAdmin) {
        keyboard = [
            [{ text: '💰 Saldo' }, { text: '📊 Harian' }, { text: '📅 Bulanan' }],
            [{ text: '🔄 Koreksi' }, { text: '💱 Rate' }, { text: '📈 Stats' }],
            [{ text: '⚙️ Config' }, { text: '👥 Users' }, { text: '📋 Transaksi' }],
            [{ text: '👑 Admin Panel' }, { text: '👑👑 Super Admin' }]
        ];
    }
    
    return {
        reply_markup: {
            keyboard: keyboard,
            resize_keyboard: true,
            one_time_keyboard: false
        }
    };
}

// ================= AI HANDLER =================
async function askAI(userMessage, userName, groupData, isAdmin = false) {
    let loadingMessage = null;
    const chatId = groupData.chatId;
    
    try {
        // Show typing indicator
        await bot.sendChatAction(chatId, 'typing');
        
        // Send loading message
        loadingMessage = await bot.sendMessage(chatId, 
            "🤔 *Hmmmm...* \n_Lagi mikir nih..._",
            { parse_mode: 'Markdown' }
        );
        
        const memory = groupData.memory;
        const now = moment().tz(groupData.config.timezone);
        
        // Prepare data for AI
        const dailyUSD = memory.dailySpent?.USD || 0;
        const dailyLimit = groupData.config.dailyLimit || CONFIG.DEFAULT_DAILY_LIMIT;
        const dailyPercent = dailyLimit > 0 ? (dailyUSD / dailyLimit) * 100 : 0;
        
        const monthlyUSD = memory.monthlySpent?.USD || 0;
        const monthlyLimit = groupData.config.monthlyLimit || CONFIG.DEFAULT_MONTHLY_LIMIT;
        const monthlyPercent = monthlyLimit > 0 ? (monthlyUSD / monthlyLimit) * 100 : 0;
        
        const recentTxns = (memory.transactions || [])
            .filter(t => !t.canceled)
            .sort((a, b) => new Date(b.time) - new Date(a.time))
            .slice(0, 5)
            .map(t => `- ${t.type === 'income' ? '📥' : t.type === 'expense' ? '📤' : '💱'} ${t.description || 'No description'}: ${t.currency === 'USD' ? `$${t.amount?.toFixed(2) || '0.00'}` : `Rp ${(t.amount || 0).toLocaleString('id-ID')}`}`)
            .join('\n') || 'Belum ada transaksi';
        
        const prompt = `Kamu adalah Finance Bot yang friendly dan santai, tapi bisa juga roast user yang boros. Kamu bisa:
1. Mencatat transaksi keuangan (income/expense/convert)
2. Memberikan informasi saldo dan statistik
3. Bercakap-cakap santai dengan user
4. Memproses perintah admin
5. Memberikan WARNING dan ROASTING kalau user melebihi limit (tapi JANGAN TOLAK transaksi!)
6. Membedakan antara transaksi harian dan bulanan. jika transaksi bulanan jangan masukkan ke limit daily

PERINGATAN PENTING: JANGAN PERNAH REJECT transaksi karena melebihi limit! Berikan warning/roasting tapi tetap proses transaksi.

DATA GRUP:
- Nama: ${groupData.name}
- User: ${userName} ${isAdmin ? '(Admin)' : ''}
- Waktu: ${now.format('HH:mm DD/MM/YYYY')} ${groupData.config.timezone}
- Saldo: IDR ${(memory.wallet?.IDR || 0).toLocaleString('id-ID')} | USD ${(memory.wallet?.USD || 0).toFixed(2)}
- Rate: 1 USD = Rp ${(memory.exchangeRate || CONFIG.DEFAULT_RATE).toLocaleString('id-ID')}
- Limit Harian: $${dailyUSD.toFixed(2)}/${dailyLimit} (${dailyPercent.toFixed(0)}%)
- Limit Bulanan: $${monthlyUSD.toFixed(2)}/${monthlyLimit} (${monthlyPercent.toFixed(0)}%)

ROASTING LEVEL (untuk pengeluaran USD):
- 80-100%: "⚠️ WARNING! Limit hampir habis, hati-hati jangan boros!"
- 100-150%: "🚨 ROASTING MEDIUM! Udah lewat limit masih nambah?"
- 150%+: "💀 ROASTING MAXIMUM! Gila lu bro, boros banget!"

TRANSAKSI TERAKHIR:
${recentTxns}

PESAN USER: "${userMessage}"

RESPOND DENGAN JSON SAJA:

{
  "type": "finance|chat|info|admin",
  "action": "income|expense|convert|cancel|rate|info|balance|history|help|chat_response|unknown",
  "amount": number,
  "currency": "IDR|USD",
  "targetCurrency": "IDR|USD",
  "targetAmount": number,
  "rate": number,
  "category": "food|transport|shopping|entertainment|bills|subscription|rent|health|education|other",
  "description": "string",
  "countsToDailyLimit": boolean,
  "error": null,
  "message": "string response dengan emoji dan friendly tone",
  "requires_confirm": boolean,
  "warning_level": "none|warning|danger|extreme",
  "warning_message": "string (berikan roasting yang lucu dan menghibur)",
  "chat_response": "string (jika type=chat)"
}`;

        // Call DeepSeek API
        const response = await axios.post(
            'https://api.deepseek.com/chat/completions',
            {
                model: 'deepseek-chat',
                messages: [
                    {
                        role: 'system',
                        content: `Kamu adalah bot keuangan yang friendly dan santai. Return HANYA JSON. Jangan ada teks lain.`
                    },
                    {
                        role: 'user',
                        content: prompt
                    }
                ],
                temperature: 0.3,
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
        
        // Update loading message
        if (loadingMessage) {
            try {
                await bot.deleteMessage(chatId, loadingMessage.message_id);
            } catch (e) {
                // Ignore deletion errors
            }
        }
        
        log('ai', `AI Response: ${aiData.type} - ${aiData.action}`, {
            user: userName,
            message: userMessage.substring(0, 100)
        });
        
        return aiData;

    } catch (error) {
        // Delete loading message if exists
        if (loadingMessage) {
            try {
                await bot.deleteMessage(chatId, loadingMessage.message_id);
            } catch (e) {
                // Ignore deletion errors
            }
        }
        
        log('error', `AI error: ${error.message}`, error.stack);
        return {
            type: "chat",
            action: "chat_response",
            message: "🤖 Waduh, otakku lagi error nih! Coba lagi ya bro!",
            chat_response: "Maaf bro, aku lagi pusing nih. Coba ulangi atau nanti aja ya! 😅",
            error: true
        };
    }
}

// ================= ACTION HANDLERS =================
async function handleCancelAction(memory, userId, time) {
    const userTxns = (memory.transactions || [])
        .filter(t => t.userId === userId && !t.canceled)
        .sort((a, b) => new Date(b.time) - new Date(a.time));
    
    if (userTxns.length === 0) {
        return {
            success: false,
            message: "❌ Gak ada transaksi yang bisa dibatalin bro!",
            type: 'finance',
            warning: null
        };
    }
    
    const lastTxn = userTxns[0];
    
    // Reverse transaction
    if (lastTxn.type === 'income') {
        if (memory.wallet) {
            memory.wallet[lastTxn.currency] = (memory.wallet[lastTxn.currency] || 0) - lastTxn.amount;
        }
    } else if (lastTxn.type === 'expense') {
        if (memory.wallet) {
            memory.wallet[lastTxn.currency] = (memory.wallet[lastTxn.currency] || 0) + lastTxn.amount;
        }
        
        // Update limits if USD expense
        if (lastTxn.currency === 'USD') {
            if (lastTxn.countsToDailyLimit && memory.dailySpent) {
                const txnTime = moment(lastTxn.time).tz(CONFIG.TIMEZONE);
                const today = moment().tz(CONFIG.TIMEZONE).format('YYYY-MM-DD');
                
                if (txnTime.format('YYYY-MM-DD') === today) {
                    memory.dailySpent.USD = Math.max(0, (memory.dailySpent.USD || 0) - lastTxn.amount);
                }
            }
        }
    } else if (lastTxn.type === 'convert') {
        if (memory.wallet) {
            memory.wallet[lastTxn.currency] = (memory.wallet[lastTxn.currency] || 0) + lastTxn.amount;
            memory.wallet[lastTxn.targetCurrency] = (memory.wallet[lastTxn.targetCurrency] || 0) - lastTxn.targetAmount;
        }
    }
    
    lastTxn.canceled = true;
    lastTxn.canceledAt = time;
    lastTxn.canceledBy = userId;
    
    await saveAllData();
    
    return {
        success: true,
        message: "✅ Transaksi terakhir berhasil dibatalin!",
        type: 'finance',
        warning: null
    };
}

async function handleRateAction(aiData, memory) {
    const rate = parseFloat(aiData.rate);
    if (rate && rate > 0) {
        const oldRate = memory.exchangeRate || CONFIG.DEFAULT_RATE;
        memory.exchangeRate = rate;
        await saveAllData();
        return {
            success: true,
            message: `💱 *Rate updated!* \n${oldRate.toLocaleString('id-ID')} → ${rate.toLocaleString('id-ID')}`,
            type: 'finance',
            warning: null
        };
    }
    return {
        success: false,
        message: "❌ Rate-nya gak valid bro!",
        type: 'finance',
        warning: null
    };
}

async function handleIncomeAction(aiData, groupData, user, chatId, txnId, time) {
    const amount = parseFloat(aiData.amount);
    const currency = aiData.currency || 'IDR';
    
    if (!amount || amount <= 0 || isNaN(amount)) {
        return {
            success: false,
            message: "❌ Jumlahnya gak valid nih!",
            type: 'finance',
            warning: null
        };
    }
    
    const config = groupData.config;
    const memory = groupData.memory;
    const isBigTransaction = amount > config.bigTransactionThreshold;
    const requiresAdminApproval = config.requireAdminForBigTransactions && isBigTransaction;
    const isAdmin = isUserAdmin(chatId, user.id);
    
    if (requiresAdminApproval && !isAdmin) {
        return {
            success: false,
            message: `⛔ *Transaksi besar nih!* \n${currency === 'USD' ? `$${amount.toFixed(2)}` : `Rp ${amount.toLocaleString('id-ID')}`} butuh persetujuan admin.`,
            type: 'finance',
            requiresAdmin: true,
            amount: amount,
            currency: currency,
            warning: null
        };
    }
    
    // Initialize wallet if not exists
    if (!memory.wallet) memory.wallet = { IDR: 0, USD: 0 };
    if (memory.wallet[currency] === undefined) memory.wallet[currency] = 0;
    
    // Add to wallet
    memory.wallet[currency] += amount;
    
    // Initialize transactions array if not exists
    if (!memory.transactions) memory.transactions = [];
    
    // Add transaction
    memory.transactions.push({
        id: txnId,
        time: time,
        user: user.name,
        userId: user.id,
        type: 'income',
        amount: amount,
        currency: currency,
        description: aiData.description || "Pemasukan",
        category: aiData.category || 'income',
        canceled: false,
        approvedBy: isAdmin ? user.name : null,
        requiresAdminApproval: requiresAdminApproval && !isAdmin
    });
    
    // Update statistics
    if (!memory.statistics) memory.statistics = { totalTransactions: 0, activeUsers: 0, lastActivity: time };
    memory.statistics.totalTransactions = (memory.statistics.totalTransactions || 0) + 1;
    memory.statistics.lastActivity = time;
    
    // Initialize users object if not exists
    if (!groupData.users) groupData.users = {};
    
    // Update user stats
    if (!groupData.users[user.id]) {
        groupData.users[user.id] = {
            name: user.name,
            transactions: 0,
            totalAmount: { IDR: 0, USD: 0 },
            lastActive: time
        };
    }
    groupData.users[user.id].transactions = (groupData.users[user.id].transactions || 0) + 1;
    groupData.users[user.id].totalAmount[currency] = (groupData.users[user.id].totalAmount[currency] || 0) + amount;
    groupData.users[user.id].lastActive = time;
    
    await saveAllData();
    
    let message = `💰 *Uang masuk!* \n${currency === 'USD' ? `$${amount.toFixed(2)}` : `Rp ${amount.toLocaleString('id-ID')}`} untuk ${aiData.description || "pemasukan"}`;
    if (isBigTransaction) {
        message += `\n\n⚠️ *Catatan:* Transaksi besar ini ${isAdmin ? 'diapprove oleh admin' : 'menunggu approval admin'}`;
    }
    
    return {
        success: true,
        message: message,
        type: 'finance',
        warning: aiData.warning_message || null
    };
}

async function handleExpenseAction(aiData, groupData, user, chatId, txnId, time) {
    const amount = parseFloat(aiData.amount);
    const currency = aiData.currency || 'IDR';
    const countsToDailyLimit = aiData.countsToDailyLimit || false;
    const category = aiData.category || 'other';
    
    if (!amount || amount <= 0 || isNaN(amount)) {
        return {
            success: false,
            message: "❌ Jumlahnya gak valid nih!",
            type: 'finance',
            warning: null
        };
    }
    
    const config = groupData.config;
    const memory = groupData.memory;
    
    // Check balance
    if (!memory.wallet) memory.wallet = { IDR: 0, USD: 0 };
    if (memory.wallet[currency] === undefined) memory.wallet[currency] = 0;
    
    if (amount > memory.wallet[currency]) {
        const needed = currency === 'USD' ?
            `$${amount.toFixed(2)}` :
            `Rp ${amount.toLocaleString('id-ID')}`;
        const current = currency === 'USD' ?
            `$${memory.wallet[currency].toFixed(2)}` :
            `Rp ${memory.wallet[currency].toLocaleString('id-ID')}`;
            
        return {
            success: false,
            message: `❌ *Gak cukup duit bro!* \nButuh: ${needed} \nSaldo: ${current}`,
            type: 'finance',
            warning: null
        };
    }
    
    let warningMessage = '';
    let warningLevel = 'none';
    
    // Check daily limit for USD expenses (WARNING ONLY, NOT REJECTION)
    if (currency === 'USD' && countsToDailyLimit) {
        if (!memory.dailySpent) memory.dailySpent = { USD: 0, limit: CONFIG.DEFAULT_DAILY_LIMIT, lastReset: moment().format('YYYY-MM-DD'), warnings: [] };
        
        const newDaily = (memory.dailySpent.USD || 0) + amount;
        const dailyLimit = config.dailyLimit || CONFIG.DEFAULT_DAILY_LIMIT;
        const dailyPercent = (newDaily / dailyLimit) * 100;
        
        // UPDATE DAILY LIMIT (ALWAYS ALLOWED)
        memory.dailySpent.USD = newDaily;
        
        // Add warning based on percentage
        if (!memory.dailySpent.warnings) memory.dailySpent.warnings = [];
        
        if (dailyPercent >= 80 && dailyPercent < 100) {
            warningMessage = `⚠️ *WARNING BOROS!*\nLimit harian hampir habis: $${newDaily.toFixed(2)}/${dailyLimit} (${dailyPercent.toFixed(0)}%)\nUdah mepet banget nih bro, hati-hati jangan boros!`;
            warningLevel = 'warning';
        } 
        else if (dailyPercent >= 100 && dailyPercent < 150) {
            warningMessage = `LIMIT HARIAN SUDAH LEWAT: $${newDaily.toFixed(2)}/${dailyLimit} (${dailyPercent.toFixed(0)}%)\n` +
                            `GILA LU BRO! Udah lewat limit masih nambah-nambah? 😡\n` +
                            `Kontrol dikit lah pengeluaran, jangan kayak anak kuliahan abis gajian!`;
            warningLevel = 'danger';
        }
        else if (dailyPercent >= 150) {
            warningMessage = `LIMIT HARIAN MELAMPAUI 150%: $${newDaily.toFixed(2)}/${dailyLimit} (${dailyPercent.toFixed(0)}%)\n` +
                            `WADUH MAKAN APA NIH KOK BOROS BANGET? 🤯\n` +
                            `Limit $${dailyLimit} aja udah lewat $${(newDaily - dailyLimit).toFixed(2)}!\n` +
                            `Besok-besok coba lebih hemat ya, jangan kayak duit gak ada besoknya!`;
            warningLevel = 'extreme';
        }
    }
    
    // Update monthly limit for USD expenses (WARNING ONLY)
    if (currency === 'USD') {
        if (!memory.monthlySpent) memory.monthlySpent = { USD: 0, limit: CONFIG.DEFAULT_MONTHLY_LIMIT, month: moment().format('YYYY-MM'), categories: {} };
        
        const newMonthly = (memory.monthlySpent.USD || 0) + amount;
        const monthlyLimit = config.monthlyLimit || CONFIG.DEFAULT_MONTHLY_LIMIT;
        const monthlyPercent = (newMonthly / monthlyLimit) * 100;
        
        memory.monthlySpent.USD = newMonthly;
        
        // Add monthly warning if needed
        if (monthlyPercent >= 80 && !warningMessage.includes('BULANAN')) {
            if (warningMessage) warningMessage += '\n\n';
            warningMessage += `📅 *WARNING BULANAN:* $${newMonthly.toFixed(2)}/${monthlyLimit} (${monthlyPercent.toFixed(0)}%)\n` +
                            `Bulan ini udah hampir abis limitnya, sisa $${(monthlyLimit - newMonthly).toFixed(2)} aja nih!`;
        }
        
        // Update category spending
        if (!memory.monthlySpent.categories) memory.monthlySpent.categories = {};
        memory.monthlySpent.categories[category] = (memory.monthlySpent.categories[category] || 0) + amount;
    }
    
    // Check if it's a big transaction
    const isBigTransaction = amount > config.bigTransactionThreshold;
    const requiresAdminApproval = config.requireAdminForBigTransactions && isBigTransaction;
    const isAdmin = isUserAdmin(chatId, user.id);
    
    if (requiresAdminApproval && !isAdmin) {
        return {
            success: false,
            message: `⛔ *Pengeluaran besar nih!* \n${currency === 'USD' ? `$${amount.toFixed(2)}` : `Rp ${amount.toLocaleString('id-ID')}`} butuh persetujuan admin.`,
            type: 'finance',
            requiresAdmin: true,
            amount: amount,
            currency: currency,
            category: category,
            warning: null
        };
    }
    
    // Deduct from wallet
    memory.wallet[currency] -= amount;
    
    // Add transaction
    if (!memory.transactions) memory.transactions = [];
    memory.transactions.push({
        id: txnId,
        time: time,
        user: user.name,
        userId: user.id,
        type: 'expense',
        amount: amount,
        currency: currency,
        description: aiData.description || "Pengeluaran",
        category: category,
        countsToDailyLimit: countsToDailyLimit,
        canceled: false,
        approvedBy: isAdmin ? user.name : null,
        requiresAdminApproval: requiresAdminApproval && !isAdmin
    });
    
    // Update statistics
    if (!memory.statistics) memory.statistics = { totalTransactions: 0, activeUsers: 0, lastActivity: time };
    memory.statistics.totalTransactions = (memory.statistics.totalTransactions || 0) + 1;
    memory.statistics.lastActivity = time;
    
    // Update user stats
    if (!groupData.users) groupData.users = {};
    if (!groupData.users[user.id]) {
        groupData.users[user.id] = {
            name: user.name,
            transactions: 0,
            totalAmount: { IDR: 0, USD: 0 },
            lastActive: time
        };
    }
    groupData.users[user.id].transactions = (groupData.users[user.id].transactions || 0) + 1;
    groupData.users[user.id].totalAmount[currency] = (groupData.users[user.id].totalAmount[currency] || 0) - amount;
    groupData.users[user.id].lastActive = time;
    
    await saveAllData();
    
    // Base message
    let fullMessage = `💸 *Duit keluar!* \n${currency === 'USD' ? `$${amount.toFixed(2)}` : `Rp ${amount.toLocaleString('id-ID')}`} untuk ${aiData.description || "pengeluaran"}`;
    
    // Add AI warning if exists
    if (aiData.warning_message) {
        fullMessage += `\n\n${aiData.warning_message}`;
    }
    
    // Add our custom warning/roasting message
    if (warningMessage) {
        fullMessage += `\n\n${warningMessage}`;
    }
    
    // Add fun roasting based on warning level
    if (warningLevel === 'danger' || warningLevel === 'extreme') {
        const roasts = [
            "💸 *Financial Advice:* Coba deh catet pengeluaran tiap hari, biar gak kaget pas liat totalnya!",
            "🍔 *Makan Tipis-tipis:* Daripada jajan mahal, mending masak sendiri lebih hemat!",
            "📱 *Subscription Check:* Cek lagi langganan yang gak kepake, bisa hemat ratusan ribu per bulan!",
            "🚌 *Transport Hack:* Naik transport umum bisa hemat 50% dari taksi/grab!",
            "💡 *Pro Tip:* Sebelum beli, tanya diri sendiri: 'Ini butuh banget atau cuma pengen aja?'"
        ];
        
        const randomRoast = roasts[Math.floor(Math.random() * roasts.length)];
        fullMessage += `\n\n${randomRoast}`;
    }
    
    if (isBigTransaction) {
        fullMessage += `\n\n⚠️ *Catatan:* Pengeluaran besar ini ${isAdmin ? 'diapprove oleh admin' : 'menunggu approval admin'}`;
    }
    
    return {
        success: true,
        message: fullMessage,
        type: 'finance',
        warning: warningMessage || aiData.warning_message || null,
        warning_level: warningLevel || aiData.warning_level || 'none'
    };
}

// ================= EXECUTE ACTION =================
async function executeAction(aiData, groupData, user, chatId) {
    const time = new Date().toISOString();
    const txnId = `txn_${Date.now()}_${Math.random().toString(36).substr(2, 6)}`;
    
    try {
        // If it's just chat or info, return immediately
        if (aiData.type === 'chat') {
            return {
                success: true,
                message: aiData.chat_response || aiData.message,
                type: 'chat',
                warning: null
            };
        }
        
        if (aiData.type === 'info') {
            // Handle info actions
            if (aiData.action === 'balance') {
                return handleBalanceInfo(groupData);
            } else if (aiData.action === 'history') {
                return handleHistoryInfo(groupData);
            } else if (aiData.action === 'help') {
                return handleHelpInfo(groupData, user.id);
            } else if (aiData.action === 'monthly') {
                return handleMonthlyInfo(groupData);
            }
            return {
                success: true,
                message: aiData.message,
                type: 'info',
                infoOnly: true,
                warning: null
            };
        }
        
        if (aiData.action === 'unknown') {
            return {
                success: false,
                message: "🤔 *Gak paham nih bro!*\nCoba kasih tau mau ngapain?\n\nContoh:\n• 'gajian 5 juta'\n• 'makan 75rb'\n• 'cek saldo'\n• 'rate 16000'",
                type: 'chat',
                warning: null
            };
        }
        
        // Check for errors
        if (aiData.error) {
            return {
                success: false,
                message: `❌ ${aiData.error}`,
                type: 'error',
                warning: null
            };
        }
        
        const action = aiData.action;
        const memory = groupData.memory;
        
        // CANCEL ACTION
        if (action === 'cancel') {
            return handleCancelAction(memory, user.id, time);
        }
        
        // RATE ACTION
        if (action === 'rate') {
            return handleRateAction(aiData, memory);
        }
        
        // INCOME ACTION
        if (action === 'income') {
            return await handleIncomeAction(aiData, groupData, user, chatId, txnId, time);
        }
        
        // EXPENSE ACTION
        if (action === 'expense') {
            return await handleExpenseAction(aiData, groupData, user, chatId, txnId, time);
        }
        
        // CONVERT ACTION
        if (action === 'convert') {
            const amount = parseFloat(aiData.amount);
            const currency = aiData.currency || 'USD';
            const targetCurrency = aiData.targetCurrency || 'IDR';
            const rate = aiData.rate || (memory.exchangeRate || CONFIG.DEFAULT_RATE);
            const targetAmount = aiData.targetAmount || (amount * rate);
            
            if (!amount || amount <= 0 || isNaN(amount)) {
                return {
                    success: false,
                    message: "❌ Jumlahnya gak valid nih!",
                    type: 'finance',
                    warning: null
                };
            }
            
            if (!memory.wallet) memory.wallet = { IDR: 0, USD: 0 };
            if (memory.wallet[currency] === undefined) memory.wallet[currency] = 0;
            
            if (amount > memory.wallet[currency]) {
                return {
                    success: false,
                    message: `❌ Saldo ${currency} gak cukup buat konversi!`,
                    type: 'finance',
                    warning: null
                };
            }
            
            // Update wallet
            memory.wallet[currency] -= amount;
            if (memory.wallet[targetCurrency] === undefined) memory.wallet[targetCurrency] = 0;
            memory.wallet[targetCurrency] += targetAmount;
            
            // Update rate if provided
            if (aiData.rate && aiData.rate > 0) {
                memory.exchangeRate = aiData.rate;
            }
            
            // Add transaction
            if (!memory.transactions) memory.transactions = [];
            memory.transactions.push({
                id: txnId,
                time: time,
                user: user.name,
                userId: user.id,
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
            
            // Update statistics
            if (!memory.statistics) memory.statistics = { totalTransactions: 0, activeUsers: 0, lastActivity: time };
            memory.statistics.totalTransactions = (memory.statistics.totalTransactions || 0) + 1;
            memory.statistics.lastActivity = time;
            
            await saveAllData();
            
            return {
                success: true,
                message: aiData.message || `💱 *Konversi berhasil!* \n${currency === 'USD' ? `$${amount.toFixed(2)}` : `Rp ${amount.toLocaleString('id-ID')}`} → ${targetCurrency === 'USD' ? `$${targetAmount.toFixed(2)}` : `Rp ${targetAmount.toLocaleString('id-ID')}`}`,
                type: 'finance',
                warning: aiData.warning_message || null
            };
        }
        
        return {
            success: false,
            message: "❌ Aksi gak dikenali nih!",
            type: 'error',
            warning: null
        };
        
    } catch (error) {
        log('error', `Execute error: ${error.message}`, error.stack);
        return {
            success: false,
            message: `❌ Error sistem: ${error.message}`,
            type: 'error',
            warning: null
        };
    }
}

// ================= INFO HANDLERS =================
function handleBalanceInfo(groupData) {
    const memory = groupData.memory;
    const wallet = memory.wallet || { IDR: 0, USD: 0 };
    const rate = memory.exchangeRate || CONFIG.DEFAULT_RATE;
    const totalWorth = wallet.IDR + (wallet.USD * rate);
    
    const dailyUSD = memory.dailySpent?.USD || 0;
    const dailyLimit = groupData.config.dailyLimit || CONFIG.DEFAULT_DAILY_LIMIT;
    const dailyPercent = dailyLimit > 0 ? (dailyUSD / dailyLimit) * 100 : 0;
    
    const monthlyUSD = memory.monthlySpent?.USD || 0;
    const monthlyLimit = groupData.config.monthlyLimit || CONFIG.DEFAULT_MONTHLY_LIMIT;
    const monthlyPercent = monthlyLimit > 0 ? (monthlyUSD / monthlyLimit) * 100 : 0;
    
    const message = `💰 *SALDO ${groupData.name}*\n\n` +
                   `📊 *Saat Ini:*\n` +
                   `├ IDR: Rp ${wallet.IDR.toLocaleString('id-ID')}\n` +
                   `├ USD: $${wallet.USD.toFixed(2)}\n` +
                   `└ *TOTAL:* Rp ${totalWorth.toLocaleString('id-ID')}\n\n` +
                   `💱 *Rate:* 1 USD = Rp ${rate.toLocaleString('id-ID')}\n\n` +
                   `🍽️ *Harian:* $${dailyUSD.toFixed(2)}/${dailyLimit} (${dailyPercent.toFixed(0)}%)\n` +
                   `📅 *Bulanan:* $${monthlyUSD.toFixed(2)}/${monthlyLimit} (${monthlyPercent.toFixed(0)}%)\n\n` +
                   `👥 *Statistik:*\n` +
                   `├ Transaksi: ${memory.statistics?.totalTransactions || 0}\n` +
                   `├ User Aktif: ${Object.keys(groupData.users || {}).length}\n` +
                   `└ Terakhir: ${moment(memory.statistics?.lastActivity || new Date()).tz(groupData.config.timezone).fromNow()}`;
    
    return {
        success: true,
        message: message,
        type: 'info',
        infoOnly: true,
        warning: null
    };
}

function handleHistoryInfo(groupData) {
    const today = moment().tz(groupData.config.timezone).format('YYYY-MM-DD');
    const todayTxns = (groupData.memory.transactions || [])
        .filter(t => !t.canceled && 
               moment(t.time).tz(groupData.config.timezone).format('YYYY-MM-DD') === today)
        .sort((a, b) => new Date(b.time) - new Date(a.time));
    
    if (todayTxns.length === 0) {
        return {
            success: true,
            message: '📊 *HARI INI*\n\nBelum ada transaksi nih bro!',
            type: 'info',
            infoOnly: true,
            warning: null
        };
    }
    
    let msgText = `📊 *TRANSAKSI HARI INI*\n`;
    msgText += `━━━━━━━━━━━━━━━━━━━━\n\n`;
    
    todayTxns.slice(0, 10).forEach((t, i) => {
        const emoji = t.type === 'income' ? '📥' : t.type === 'expense' ? '📤' : '💱';
        const amount = t.currency === 'USD' ? 
            `$${t.amount?.toFixed(2) || '0.00'}` : 
            `Rp ${(t.amount || 0).toLocaleString('id-ID')}`;
        const time = moment(t.time).tz(groupData.config.timezone).format('HH:mm');
        
        msgText += `${emoji} *${t.description || 'No description'}*\n`;
        if (t.type === 'convert') {
            const targetAmount = t.targetCurrency === 'USD' ?
                `$${t.targetAmount?.toFixed(2) || '0.00'}` :
                `Rp ${(t.targetAmount || 0).toLocaleString('id-ID')}`;
            msgText += `   ${amount} → ${targetAmount}\n`;
        } else {
            msgText += `   ${amount}\n`;
        }
        msgText += `   👤 ${t.user} • 🕐 ${time}\n\n`;
    });
    
    if (todayTxns.length > 10) {
        msgText += `\n...dan ${todayTxns.length - 10} transaksi lainnya`;
    }
    
    return {
        success: true,
        message: msgText,
        type: 'info',
        infoOnly: true,
        warning: null
    };
}

function handleMonthlyInfo(groupData) {
    const memory = groupData.memory;
    const monthly = memory.monthlySpent || { USD: 0, limit: CONFIG.DEFAULT_MONTHLY_LIMIT, month: moment().format('YYYY-MM'), categories: {} };
    const monthlyLimit = groupData.config.monthlyLimit || CONFIG.DEFAULT_MONTHLY_LIMIT;
    const monthlyPercent = monthlyLimit > 0 ? (monthly.USD / monthlyLimit) * 100 : 0;
    
    let msgText = `📅 *LAPORAN BULANAN* (${monthly.month})\n`;
    msgText += `━━━━━━━━━━━━━━━━━━━━\n\n`;
    
    msgText += `💰 *Total Pengeluaran:* $${monthly.USD.toFixed(2)}/${monthlyLimit} (${monthlyPercent.toFixed(0)}%)\n\n`;
    
    // Kategori pengeluaran
    if (monthly.categories && Object.keys(monthly.categories).length > 0) {
        msgText += `📊 *Pengeluaran per Kategori:*\n`;
        
        const categories = Object.entries(monthly.categories)
            .sort(([,a], [,b]) => b - a);
        
        categories.forEach(([category, amount]) => {
            const percent = monthly.USD > 0 ? (amount / monthly.USD) * 100 : 0;
            const barLength = Math.round(percent / 5);
            const bar = '█'.repeat(barLength) + '░'.repeat(20 - barLength);
            
            msgText += `├ ${getCategoryEmoji(category)} ${category}: $${amount.toFixed(2)}\n`;
            msgText += `│   ${bar} ${percent.toFixed(0)}%\n`;
        });
    } else {
        msgText += `📊 *Kategori:* Belum ada pengeluaran bulan ini\n`;
    }
    
    // Transaksi bulan ini
    const currentMonth = moment().format('YYYY-MM');
    const monthlyTxns = (memory.transactions || [])
        .filter(t => !t.canceled && 
               moment(t.time).format('YYYY-MM') === currentMonth &&
               t.type === 'expense')
        .sort((a, b) => new Date(b.time) - new Date(a.time));
    
    if (monthlyTxns.length > 0) {
        msgText += `\n💸 *Transaksi Bulan Ini:*\n`;
        monthlyTxns.slice(0, 5).forEach((t, i) => {
            const amount = t.currency === 'USD' ? 
                `$${t.amount?.toFixed(2) || '0.00'}` : 
                `Rp ${(t.amount || 0).toLocaleString('id-ID')}`;
            const date = moment(t.time).format('DD/MM');
            
            msgText += `├ ${getCategoryEmoji(t.category)} ${amount} - ${t.description || 'No description'}\n`;
            msgText += `│   👤 ${t.user} • 📅 ${date}\n`;
        });
        
        if (monthlyTxns.length > 5) {
            msgText += `└ ...dan ${monthlyTxns.length - 5} transaksi lainnya`;
        }
    }
    
    // Sisa budget
    const remaining = monthlyLimit - monthly.USD;
    if (remaining > 0) {
        const daysLeft = moment().endOf('month').diff(moment(), 'days');
        const dailyBudget = remaining / Math.max(daysLeft, 1);
        
        msgText += `\n\n💰 *Sisa Budget:* $${remaining.toFixed(2)}\n`;
        msgText += `📅 *Hari tersisa:* ${daysLeft} hari\n`;
        msgText += `🍽️ *Budget harian:* $${dailyBudget.toFixed(2)}/hari`;
    } else if (remaining < 0) {
        msgText += `\n\n⚠️ *OVER BUDGET!* Kelebihan: $${Math.abs(remaining).toFixed(2)}`;
    } else {
        msgText += `\n\n✅ *Budget pas!* Tidak ada sisa budget`;
    }
    
    return {
        success: true,
        message: msgText,
        type: 'info',
        infoOnly: true,
        warning: null
    };
}

function getCategoryEmoji(category) {
    const emojis = {
        food: '🍔', transport: '🚗', shopping: '🛍️',
        entertainment: '🎮', bills: '🧾', subscription: '📱',
        rent: '🏠', health: '💊', education: '📚',
        other: '📦', income: '💰', convert: '💱'
    };
    return emojis[category] || '📝';
}

function handleHelpInfo(groupData, userId) {
    const isAdmin = isUserAdmin(groupData.chatId, userId);
    const isSuperAdmin = CONFIG.SUPER_ADMIN_IDS.includes(parseInt(userId));
    
    let helpText = `🤖 *FINANCE BOT HELP*\n━━━━━━━━━━━━━━━━━━━━\n\n`;
    
    // Tampilkan tombol berdasarkan user role
    if (isSuperAdmin) {
        helpText += `👑👑 *SUPER ADMIN MENU:*\n`;
        helpText += `• 💰 Saldo - Cek saldo grup\n`;
        helpText += `• 📊 Harian - Transaksi hari ini\n`;
        helpText += `• 📅 Bulanan - Laporan bulanan\n`;
        helpText += `• 🔄 Koreksi - Batalkan transaksi\n`;
        helpText += `• ❓ Bantuan - Panduan ini\n`;
        helpText += `• 💱 Rate - Lihat rate USD\n`;
        helpText += `• 📈 Stats - Statistik grup\n`;
        helpText += `• ⚙️ Config - Pengaturan grup\n`;
        helpText += `• 👥 Users - Daftar user\n`;
        helpText += `• 📋 Transaksi - List transaksi\n`;
        helpText += `• 👑 Admin Panel - Menu admin\n`;
        helpText += `• 👑👑 Super Admin - Super admin panel\n\n`;
    } else if (isAdmin) {
        helpText += `👑 *ADMIN MENU:*\n`;
        helpText += `• 💰 Saldo - Cek saldo grup\n`;
        helpText += `• 📊 Harian - Transaksi hari ini\n`;
        helpText += `• 📅 Bulanan - Laporan bulanan\n`;
        helpText += `• 🔄 Koreksi - Batalkan transaksi\n`;
        helpText += `• ❓ Bantuan - Panduan ini\n`;
        helpText += `• 💱 Rate - Lihat rate USD\n`;
        helpText += `• 📈 Stats - Statistik grup\n`;
        helpText += `• ⚙️ Config - Pengaturan grup\n`;
        helpText += `• 👥 Users - Daftar user\n`;
        helpText += `• 📋 Transaksi - List transaksi\n`;
        helpText += `• 👑 Admin Panel - Menu admin\n\n`;
    } else {
        helpText += `👤 *USER MENU:*\n`;
        helpText += `• 💰 Saldo - Cek saldo grup\n`;
        helpText += `• 📊 Harian - Transaksi hari ini\n`;
        helpText += `• 📅 Bulanan - Laporan bulanan\n`;
        helpText += `• 🔄 Koreksi - Batalkan transaksi\n`;
        helpText += `• ❓ Bantuan - Panduan ini\n`;
        helpText += `• 💱 Rate - Lihat rate USD\n`;
        helpText += `• 📈 Stats - Statistik grup\n\n`;
    }
    
    helpText += `💬 *Cara pakai:*\n`;
    helpText += `• "gajian 5 juta" - Tambah pemasukan\n`;
    helpText += `• "makan 75rb" - Catat pengeluaran\n`;
    helpText += `• "jajan 10 dollar" - Pengeluaran USD\n`;
    helpText += `• "rate 16000" - Update kurs\n`;
    helpText += `• "salah tadi" - Batalkan transaksi\n`;
    helpText += `• "cek saldo" - Lihat saldo\n`;
    helpText += `• "hari ini" - Transaksi hari ini\n`;
    helpText += `• "bulan ini" - Laporan bulanan\n\n`;
    
    if (isAdmin) {
        helpText += `👑 *Admin Commands:*\n`;
        helpText += `• /config - Lihat pengaturan grup\n`;
        helpText += `• /setlimit [harian] [bulanan] - Set limit\n`;
        helpText += `• /addadmin [user_id] - Tambah admin\n`;
        helpText += `• /enablechat - Aktifkan fitur chat\n`;
        helpText += `• /disablechat - Nonaktifkan fitur chat\n`;
        helpText += `• /stats - Statistik grup\n`;
        helpText += `• /users - Daftar user\n`;
        helpText += `• /approve - Approve transaksi besar\n`;
        helpText += `• /enable - Aktifkan bot\n`;
        helpText += `• /disable - Nonaktifkan bot\n`;
        helpText += `• /reset [type] - Reset data\n\n`;
    }
    
    if (isSuperAdmin) {
        helpText += `👑👑 *SUPER ADMIN:*\n`;
        helpText += `• /super whitelist [add/remove/list/clear] [chat_id]\n`;
        helpText += `• /super blacklist [add/remove/list/clear] [chat_id]\n`;
        helpText += `• /super autoapprove [on/off/status]\n`;
        helpText += `• /super listgroups\n`;
        helpText += `• /super broadcast [pesan]\n`;
        helpText += `• /super status [chat_id]\n`;
        helpText += `• /super fix [chat_id]\n`;
    }
    
    helpText += `\n🏷️ *Grup ID:* ${groupData.chatId}`;
    if (isSuperAdmin) {
        helpText += `\n🔑 *User ID:* ${userId}`;
    }
    
    return {
        success: true,
        message: helpText,
        type: 'info',
        infoOnly: true,
        warning: null
    };
}

// ================= ADMIN FUNCTIONS =================
async function handleAdminCommand(chatId, userId, command, args = []) {
    const isSuperAdmin = CONFIG.SUPER_ADMIN_IDS.includes(parseInt(userId));
    const groupData = getGroupData(chatId);
    const isGroupAdmin = isUserAdmin(chatId, userId);
    
    if (!isSuperAdmin && !isGroupAdmin) {
        return "⛔ *Gak punya akses bro!* Hanya admin yang bisa pake command ini.";
    }
    
    if (!groupData) {
        return "❌ Grup belum terdaftar atau belum diapprove!";
    }
    
    const cmd = command.toLowerCase();
    
    switch (cmd) {
        case '/config':
            return showGroupConfig(groupData);
            
        case '/setlimit':
            return await setGroupLimit(chatId, args, groupData);
            
        case '/addadmin':
            return await addGroupAdmin(chatId, args, groupData, userId, isSuperAdmin);
            
        case '/removeadmin':
            return await removeGroupAdmin(chatId, args, groupData, userId, isSuperAdmin);
            
        case '/enable':
            return await enableGroup(chatId, groupData);
            
        case '/disable':
            return await disableGroup(chatId, groupData);
            
        case '/reset':
            return await resetGroupData(chatId, args, groupData);
            
        case '/stats':
            return showGroupStats(groupData);
            
        case '/users':
            return showGroupUsers(groupData);
            
        case '/approve':
            return await approveTransaction(chatId, args, groupData, userId);
            
        case '/enablechat':
            return await toggleChatFeature(chatId, groupData, true);
            
        case '/disablechat':
            return await toggleChatFeature(chatId, groupData, false);
            
        case '/transactions':
            return await showTransactions(chatId, args, groupData, userId);
            
        case '/super':
            if (!isSuperAdmin) return "⛔ Hanya Super Admin yang bisa pakai command ini!";
            return await handleSuperAdminCommand(args, chatId);
            
        default:
            return "❌ Command admin gak dikenal. Coba /config, /setlimit, /addadmin, etc.";
    }
}

async function toggleChatFeature(chatId, groupData, enable) {
    if (!groupData.config) {
        groupData.config = {};
    }
    
    groupData.config.enableChat = enable;
    await saveAllData();
    
    log('admin', `Chat feature ${enable ? 'enabled' : 'disabled'} in group ${chatId}`, {
        name: groupData.name,
        enableChat: groupData.config.enableChat
    });
    
    return `✅ Fitur chat ${enable ? 'diaktifkan' : 'dinonaktifkan'}!\n\n` +
           `Sekarang bot akan ${enable ? 'merespon chat biasa' : 'hanya merespon command dan tombol'}.`;
}

function showGroupConfig(groupData) {
    return `
👑 *KONFIGURASI ${groupData.name || 'Group'}*

📊 *Limits:*
├ Harian: $${groupData.config.dailyLimit || CONFIG.DEFAULT_DAILY_LIMIT}
├ Bulanan: $${groupData.config.monthlyLimit || CONFIG.DEFAULT_MONTHLY_LIMIT}
└ Big Transaction: Rp ${(groupData.config.bigTransactionThreshold || 1000000).toLocaleString('id-ID')}

⚙️ *Settings:*
├ Auto-reset harian: ${groupData.config.autoResetDaily ? '✅' : '❌'}
├ Notify on limit: ${groupData.config.notifyOnLimit ? '✅' : '❌'}
├ Admin untuk transaksi besar: ${groupData.config.requireAdminForBigTransactions ? '✅' : '❌'}
├ Allow all members: ${groupData.config.allowAllMembers ? '✅' : '❌'}
├ Enable chat: ${groupData.config.enableChat !== false ? '✅' : '❌'}
└ Timezone: ${groupData.config.timezone || CONFIG.TIMEZONE}

👑 *Admins:* ${groupData.admins && groupData.admins.length > 0 ? groupData.admins.map(a => `\n├ ${a}`).join('') : '\n├ Belum ada admin'}

📊 *Status:* ${groupData.enabled ? '✅ Aktif' : '❌ Nonaktif'}
`;
}

async function setGroupLimit(chatId, args, groupData) {
    if (args.length < 2) {
        return "❌ Format: /setlimit [harian] [bulanan]\nContoh: /setlimit 30 1500";
    }
    
    const daily = parseFloat(args[0]);
    const monthly = parseFloat(args[1]);
    
    if (isNaN(daily) || daily <= 0 || isNaN(monthly) || monthly <= 0) {
        return "❌ Angka harus valid dan lebih dari 0!";
    }
    
    groupData.config.dailyLimit = daily;
    groupData.config.monthlyLimit = monthly;
    if (groupData.memory.dailySpent) {
        groupData.memory.dailySpent.limit = daily;
    }
    if (groupData.memory.monthlySpent) {
        groupData.memory.monthlySpent.limit = monthly;
    }
    
    await saveAllData();
    
    return `✅ Limits updated!\nHarian: $${daily}\nBulanan: $${monthly}`;
}

async function addGroupAdmin(chatId, args, groupData, userId, isSuperAdmin) {
    if (args.length < 1) {
        return "❌ Format: /addadmin [user_id]";
    }
    
    const newAdmin = args[0].toString();
    
    if (!groupData.admins) groupData.admins = [];
    
    if (groupData.admins.includes(newAdmin)) {
        return "❌ User sudah jadi admin!";
    }
    
    groupData.admins.push(newAdmin);
    await saveAllData();
    
    return `✅ User ${newAdmin} ditambahkan sebagai admin!`;
}

async function removeGroupAdmin(chatId, args, groupData, userId, isSuperAdmin) {
    if (args.length < 1) {
        return "❌ Format: /removeadmin [user_id]";
    }
    
    const adminToRemove = args[0].toString();
    
    if (adminToRemove === userId.toString() && !isSuperAdmin) {
        return "❌ Gak bisa hapus diri sendiri!";
    }
    
    if (!groupData.admins) return "❌ Tidak ada admin di grup ini!";
    
    const index = groupData.admins.indexOf(adminToRemove);
    if (index === -1) {
        return "❌ User bukan admin!";
    }
    
    groupData.admins.splice(index, 1);
    await saveAllData();
    
    return `✅ User ${adminToRemove} dihapus dari admin!`;
}

async function enableGroup(chatId, groupData) {
    if (groupData.enabled === true) {
        return "ℹ️ Bot sudah aktif di grup ini!";
    }
    
    groupData.enabled = true;
    await saveAllData();
    
    log('admin', `Bot enabled in group ${chatId}`, { 
        name: groupData.name,
        enabled: groupData.enabled 
    });
    
    // Kirim welcome message dengan keyboard
    const keyboard = getGroupKeyboard(chatId, chatId);
    await bot.sendMessage(chatId,
        `🤖 *FINANCE BOT - AKTIF!*\n\n` +
        `Bot sudah diaktifkan di grup ${groupData.name}!\n\n` +
        `Sekarang semua member bisa:\n` +
        `• Mencatat transaksi\n` +
        `• Mengecek saldo\n` +
        `• Menggunakan tombol di bawah👇\n\n` +
        `Selamat menggunakan! 🎉`,
        {
            parse_mode: 'Markdown',
            reply_markup: keyboard.reply_markup
        }
    );
    
    return `✅ Bot diaktifkan di grup ini!\n\nGrup: ${groupData.name}\nStatus: ✅ Aktif`;
}

async function disableGroup(chatId, groupData) {
    if (groupData.enabled === false) {
        return "ℹ️ Bot sudah nonaktif di grup ini!";
    }
    
    groupData.enabled = false;
    await saveAllData();
    
    log('admin', `Bot disabled in group ${chatId}`, { 
        name: groupData.name,
        enabled: groupData.enabled 
    });
    
    return `✅ Bot dinonaktifkan di grup ini!\n\nGrup: ${groupData.name}\nStatus: ❌ Nonaktif\n\nUntuk mengaktifkan kembali, gunakan /enable`;
}

async function resetGroupData(chatId, args, groupData) {
    const resetType = args[0] || 'all';
    
    switch (resetType) {
        case 'daily':
            if (groupData.memory.dailySpent) {
                groupData.memory.dailySpent.USD = 0;
                groupData.memory.dailySpent.warnings = [];
            }
            break;
        case 'monthly':
            if (groupData.memory.monthlySpent) {
                groupData.memory.monthlySpent.USD = 0;
                groupData.memory.monthlySpent.categories = {};
            }
            break;
        case 'wallet':
            groupData.memory.wallet = { IDR: 0, USD: 0 };
            break;
        case 'transactions':
            groupData.memory.transactions = [];
            if (groupData.memory.statistics) {
                groupData.memory.statistics.totalTransactions = 0;
            }
            break;
        case 'all':
            const newData = createNewGroupData(chatId.toString());
            groupData.memory = newData.memory;
            break;
        default:
            return "❌ Jenis reset tidak dikenal. Pilih: daily, monthly, wallet, transactions, all";
    }
    
    await saveAllData();
    return `✅ Data ${resetType} berhasil direset!`;
}

function showGroupStats(groupData) {
    const memory = groupData.memory;
    const now = moment().tz(groupData.config.timezone);
    
    const dailyUSD = memory.dailySpent?.USD || 0;
    const dailyLimit = groupData.config.dailyLimit || CONFIG.DEFAULT_DAILY_LIMIT;
    const dailyPercent = dailyLimit > 0 ? (dailyUSD / dailyLimit) * 100 : 0;
    
    const monthlyUSD = memory.monthlySpent?.USD || 0;
    const monthlyLimit = groupData.config.monthlyLimit || CONFIG.DEFAULT_MONTHLY_LIMIT;
    const monthlyPercent = monthlyLimit > 0 ? (monthlyUSD / monthlyLimit) * 100 : 0;
    
    const wallet = memory.wallet || { IDR: 0, USD: 0 };
    const rate = memory.exchangeRate || CONFIG.DEFAULT_RATE;
    const totalWorth = wallet.IDR + (wallet.USD * rate);
    
    let stats = `📊 *STATISTIK ${groupData.name || 'Group'}*\n\n`;
    
    stats += `💰 *Financial:*\n`;
    stats += `├ Total Worth: Rp ${totalWorth.toLocaleString('id-ID')}\n`;
    stats += `├ IDR: Rp ${wallet.IDR.toLocaleString('id-ID')}\n`;
    stats += `├ USD: $${wallet.USD.toFixed(2)}\n`;
    stats += `└ Rate: 1 USD = Rp ${rate.toLocaleString('id-ID')}\n\n`;
    
    stats += `📈 *Usage:*\n`;
    stats += `├ Harian: $${dailyUSD.toFixed(2)}/${dailyLimit} (${dailyPercent.toFixed(0)}%)\n`;
    stats += `└ Bulanan: $${monthlyUSD.toFixed(2)}/${monthlyLimit} (${monthlyPercent.toFixed(0)}%)\n\n`;
    
    const totalTransactions = memory.statistics?.totalTransactions || 0;
    const canceledTxns = (memory.transactions || []).filter(t => t.canceled).length;
    const lastActivity = memory.statistics?.lastActivity || new Date().toISOString();
    
    stats += `📝 *Transactions:*\n`;
    stats += `├ Total: ${totalTransactions}\n`;
    stats += `├ Canceled: ${canceledTxns}\n`;
    stats += `└ Last: ${moment(lastActivity).tz(groupData.config.timezone).fromNow()}\n\n`;
    
    const userCount = Object.keys(groupData.users || {}).length;
    stats += `👥 *Users:*\n`;
    stats += `├ Total: ${userCount}\n`;
    
    if (userCount > 0) {
        const users = Object.values(groupData.users || {});
        const topUser = users.sort((a, b) => (b.transactions || 0) - (a.transactions || 0))[0];
        if (topUser) {
            stats += `├ Top User: ${topUser.name} (${topUser.transactions || 0} txn)\n`;
        }
        
        const activeUsers = users.filter(u => 
            moment(u.lastActive).isAfter(now.clone().subtract(7, 'days'))).length;
        stats += `└ Active (7d): ${activeUsers}`;
    } else {
        stats += `└ Active (7d): 0`;
    }
    
    return stats;
}

function showGroupUsers(groupData) {
    const users = Object.values(groupData.users || {});
    
    if (users.length === 0) {
        return "👥 *USERS*\n\nBelum ada user yang aktif!";
    }
    
    let userList = `👥 *USERS ${groupData.name || 'Group'}*\n━━━━━━━━━━━━━━━━━━━━\n\n`;
    
    const rate = groupData.memory.exchangeRate || CONFIG.DEFAULT_RATE;
    
    users.sort((a, b) => (b.transactions || 0) - (a.transactions || 0))
        .slice(0, 15)
        .forEach((user, index) => {
            userList += `${index + 1}. *${user.name}*\n`;
            userList += `   📊 Txns: ${user.transactions || 0}\n`;
            
            const totalAmount = (user.totalAmount?.IDR || 0) + ((user.totalAmount?.USD || 0) * rate);
            const amountText = totalAmount >= 0 ? 
                `💰 Total: Rp ${totalAmount.toLocaleString('id-ID')}` :
                `💸 Pengeluaran: Rp ${Math.abs(totalAmount).toLocaleString('id-ID')}`;
            
            userList += `   ${amountText}\n`;
            userList += `   ⏰ Last: ${moment(user.lastActive).tz(groupData.config.timezone).fromNow()}\n\n`;
        });
    
    if (users.length > 15) {
        userList += `\n...dan ${users.length - 15} user lainnya`;
    }
    
    // Summary
    const totalTxns = users.reduce((sum, user) => sum + (user.transactions || 0), 0);
    const totalIDR = users.reduce((sum, user) => sum + (user.totalAmount?.IDR || 0), 0);
    const totalUSD = users.reduce((sum, user) => sum + (user.totalAmount?.USD || 0), 0);
    const totalWorth = totalIDR + (totalUSD * rate);
    
    userList += `━━━━━━━━━━━━━━━━━━━━\n`;
    userList += `📊 *Summary:*\n`;
    userList += `├ Total Users: ${users.length}\n`;
    userList += `├ Total Transaksi: ${totalTxns}\n`;
    userList += `└ Total Worth: Rp ${totalWorth.toLocaleString('id-ID')}`;
    
    return userList;
}

async function approveTransaction(chatId, args, groupData, userId) {
    // Find pending transaction
    const pendingTxns = (groupData.memory.transactions || [])
        .filter(t => t.requiresAdminApproval && !t.approvedBy && !t.canceled);
    
    if (pendingTxns.length === 0) {
        return "❌ Tidak ada transaksi yang butuh approval!";
    }
    
    const txnId = args[0];
    if (!txnId) {
        let response = `📋 *PENDING APPROVALS*\n\n`;
        pendingTxns.forEach((t, i) => {
            response += `${i+1}. ${t.type === 'income' ? '📥' : '📤'} ${t.description || 'No description'}\n`;
            response += `   Jumlah: ${t.currency === 'USD' ? `$${t.amount?.toFixed(2) || '0.00'}` : `Rp ${(t.amount || 0).toLocaleString('id-ID')}`}\n`;
            response += `   User: ${t.user}\n`;
            response += `   ID: ${t.id}\n\n`;
        });
        response += `\nGunakan: /approve [transaction_id]`;
        return response;
    }
    
    const txn = (groupData.memory.transactions || []).find(t => t.id === txnId);
    if (!txn) {
        return "❌ Transaksi tidak ditemukan!";
    }
    
    const userName = groupData.users[userId]?.name || `Admin ${userId}`;
    txn.approvedBy = userName;
    txn.requiresAdminApproval = false;
    
    // Jika income, tambahkan ke wallet
    if (txn.type === 'income' && !txn.canceled) {
        if (!groupData.memory.wallet) groupData.memory.wallet = { IDR: 0, USD: 0 };
        if (groupData.memory.wallet[txn.currency] === undefined) groupData.memory.wallet[txn.currency] = 0;
        groupData.memory.wallet[txn.currency] += txn.amount;
    }
    
    await saveAllData();
    
    return `✅ Transaksi ${txnId} berhasil diapprove oleh ${userName}!`;
}

async function showTransactions(chatId, args, groupData, userId) {
    const days = parseInt(args[0]) || 7;
    const memory = groupData.memory;
    
    const now = moment();
    const startDate = now.clone().subtract(days, 'days');
    
    const recentTxns = (memory.transactions || [])
        .filter(t => moment(t.time).isAfter(startDate) && !t.canceled)
        .sort((a, b) => new Date(b.time) - new Date(a.time));
    
    if (recentTxns.length === 0) {
        return `📋 *TRANSAKSI (${days} hari terakhir)*\n\nBelum ada transaksi nih bro!`;
    }
    
    let msgText = `📋 *TRANSAKSI ${days} HARI TERAKHIR*\n`;
    msgText += `━━━━━━━━━━━━━━━━━━━━\n\n`;
    
    let totalIncome = { IDR: 0, USD: 0 };
    let totalExpense = { IDR: 0, USD: 0 };
    
    recentTxns.slice(0, 20).forEach((t, i) => {
        const emoji = t.type === 'income' ? '📥' : t.type === 'expense' ? '📤' : '💱';
        const amount = t.currency === 'USD' ? 
            `$${t.amount?.toFixed(2) || '0.00'}` : 
            `Rp ${(t.amount || 0).toLocaleString('id-ID')}`;
        const time = moment(t.time).tz(groupData.config.timezone).format('DD/MM HH:mm');
        
        msgText += `${emoji} *${t.description || 'No description'}*\n`;
        if (t.type === 'convert') {
            const targetAmount = t.targetCurrency === 'USD' ?
                `$${t.targetAmount?.toFixed(2) || '0.00'}` :
                `Rp ${(t.targetAmount || 0).toLocaleString('id-ID')}`;
            msgText += `   ${amount} → ${targetAmount}\n`;
        } else {
            msgText += `   ${amount}\n`;
            
            // Update totals
            if (t.type === 'income') {
                totalIncome[t.currency] = (totalIncome[t.currency] || 0) + t.amount;
            } else if (t.type === 'expense') {
                totalExpense[t.currency] = (totalExpense[t.currency] || 0) + t.amount;
            }
        }
        msgText += `   👤 ${t.user} • 🕐 ${time}\n\n`;
    });
    
    if (recentTxns.length > 20) {
        msgText += `\n...dan ${recentTxns.length - 20} transaksi lainnya`;
    }
    
    // Summary
    const rate = memory.exchangeRate || CONFIG.DEFAULT_RATE;
    const totalIncomeIDR = totalIncome.IDR + (totalIncome.USD * rate);
    const totalExpenseIDR = totalExpense.IDR + (totalExpense.USD * rate);
    const netCashflow = totalIncomeIDR - totalExpenseIDR;
    
    msgText += `\n━━━━━━━━━━━━━━━━━━━━\n`;
    msgText += `💰 *SUMMARY (${days} hari):*\n`;
    msgText += `├ 📥 Pemasukan: Rp ${totalIncomeIDR.toLocaleString('id-ID')}\n`;
    msgText += `├ 📤 Pengeluaran: Rp ${totalExpenseIDR.toLocaleString('id-ID')}\n`;
    if (netCashflow >= 0) {
        msgText += `└ ✅ Net: +Rp ${netCashflow.toLocaleString('id-ID')}`;
    } else {
        msgText += `└ ❌ Net: -Rp ${Math.abs(netCashflow).toLocaleString('id-ID')}`;
    }
    
    return msgText;
}

// ================= SUPER ADMIN FUNCTIONS =================
async function handleSuperAdminCommand(args, chatId) {
    const [cmd, ...params] = args;
    
    if (!cmd) {
        return await showSuperAdminPanel(chatId);
    }
    
    switch (cmd.toLowerCase()) {
        case 'whitelist':
            return await manageWhitelist(params, chatId);
            
        case 'blacklist':
            return await manageBlacklist(params, chatId);
            
        case 'autoapprove':
            return await toggleAutoApprove(params);
            
        case 'listgroups':
            return await showAllGroupsPanel(chatId);
            
        case 'broadcast':
            return await broadcastMessage(params);
            
        case 'status':
            return await showGroupStatus(params, chatId);
            
        case 'fix':
            return await fixGroup(params, chatId);
            
        case 'panel':
            return await showSuperAdminPanel(chatId);
            
        case 'backup':
            return await createBackup(chatId);
            
        case 'restore':
            return await restoreBackup(params, chatId);
            
        case 'delete':
            return await deleteGroup(params, chatId);
            
        case 'migrate':
            return await migrateGroupData(params, chatId);
            
        default:
            return "❌ Super admin command gak dikenal. Gunakan tombol 👑👑 Super Admin untuk panel lengkap.";
    }
}

async function showSuperAdminPanel(chatId) {
    const totalGroups = Object.keys(groupsData).length;
    const activeGroups = Object.values(groupsData).filter(g => g.enabled).length;
    const totalUsers = Object.values(groupsData).reduce((sum, g) => sum + Object.keys(g.users || {}).length, 0);
    const totalTransactions = Object.values(groupsData).reduce((sum, g) => sum + (g.memory?.statistics?.totalTransactions || 0), 0);
    
    const panel = `👑👑 *SUPER ADMIN PANEL*\n━━━━━━━━━━━━━━━━━━━━\n\n` +
                 `📊 *Global Statistics:*\n` +
                 `├ Total Grup: ${totalGroups}\n` +
                 `├ Grup Aktif: ${activeGroups}\n` +
                 `├ Total Users: ${totalUsers}\n` +
                 `├ Total Transaksi: ${totalTransactions}\n` +
                 `├ Whitelist: ${globalConfig.whitelist.length}\n` +
                 `├ Blacklist: ${globalConfig.blacklist.length}\n` +
                 `└ Auto Approve: ${globalConfig.autoApprove ? '✅ ON' : '❌ OFF'}\n\n` +
                 
                 `⚡ *Quick Actions:*\n` +
                 `• /super whitelist add [id] - Tambah grup ke whitelist\n` +
                 `• /super blacklist add [id] - Blokir grup\n` +
                 `• /super autoapprove on - Auto approve semua grup\n` +
                 `• /super listgroups - List semua grup\n` +
                 `• /super broadcast [pesan] - Broadcast ke semua grup\n\n` +
                 
                 `🔧 *Advanced Tools:*\n` +
                 `• /super status [chat_id] - Cek status grup\n` +
                 `• /super fix [chat_id] - Fix grup bermasalah\n` +
                 `• /super backup - Buat backup data\n` +
                 `• /super delete [chat_id] - Hapus grup\n` +
                 `• /super migrate [old] [new] - Migrasi data grup\n\n` +
                 
                 `📱 *Panel Navigation:*\n` +
                 `Gunakan tombol di bawah untuk navigasi cepat!`;
    
    const keyboard = {
        reply_markup: {
            inline_keyboard: [
                [
                    { text: '📋 List Groups', callback_data: 'super_listgroups' },
                    { text: '⚙️ Global Config', callback_data: 'super_config' }
                ],
                [
                    { text: '📊 Statistics', callback_data: 'super_stats' },
                    { text: '🔧 Tools', callback_data: 'super_tools' }
                ],
                [
                    { text: '🔄 Refresh', callback_data: 'super_refresh' },
                    { text: '❌ Close', callback_data: 'super_close' }
                ]
            ]
        }
    };
    
    return { text: panel, keyboard };
}

async function showAllGroupsPanel(chatId) {
    const groups = Object.entries(groupsData);
    
    if (groups.length === 0) {
        return "📋 *ALL GROUPS*\n\nBelum ada grup yang terdaftar!";
    }
    
    let list = `📋 *ALL GROUPS (${groups.length})*\n━━━━━━━━━━━━━━━━━━━━\n\n`;
    
    groups.sort(([,a], [,b]) => new Date(b.created) - new Date(a.created))
        .slice(0, 15)
        .forEach(([chatId, data], index) => {
            const wallet = data.memory.wallet || { IDR: 0, USD: 0 };
            const rate = data.memory.exchangeRate || CONFIG.DEFAULT_RATE;
            const totalWorth = wallet.IDR + (wallet.USD * rate);
            
            const dailyUSD = data.memory.dailySpent?.USD || 0;
            const dailyLimit = data.config.dailyLimit || CONFIG.DEFAULT_DAILY_LIMIT;
            const dailyPercent = dailyLimit > 0 ? (dailyUSD / dailyLimit) * 100 : 0;
            
            list += `${index + 1}. *${data.name || 'Unnamed Group'}*\n`;
            list += `   📍 ID: ${chatId}\n`;
            list += `   💰 Worth: Rp ${totalWorth.toLocaleString('id-ID')}\n`;
            list += `   📊 Usage: ${dailyPercent.toFixed(0)}%\n`;
            list += `   👥 Users: ${Object.keys(data.users || {}).length}\n`;
            list += `   ⚙️ Status: ${data.enabled ? '✅ Aktif' : '❌ Nonaktif'}\n`;
            list += `   👑 Admins: ${data.admins?.length || 0}\n`;
            list += `   🕐 Created: ${moment(data.created).fromNow()}\n\n`;
        });
    
    if (groups.length > 15) {
        list += `\n...dan ${groups.length - 15} grup lainnya`;
    }
    
    const keyboard = {
        reply_markup: {
            inline_keyboard: [
                [
                    { text: '📊 Statistics', callback_data: 'super_stats' },
                    { text: '⚙️ Config', callback_data: 'super_config' }
                ],
                [
                    { text: '🔙 Back to Panel', callback_data: 'super_panel' },
                    { text: '🔄 Refresh', callback_data: 'super_listgroups' }
                ]
            ]
        }
    };
    
    return { text: list, keyboard };
}

async function manageWhitelist(params, chatId) {
    const [action, ...ids] = params;
    
    if (!action || !['add', 'remove', 'list', 'clear'].includes(action)) {
        return "❌ Format: /super whitelist [add/remove/list/clear] [chat_id...]\nContoh: /super whitelist add 123456789";
    }
    
    if (action === 'list') {
        const list = globalConfig.whitelist.length > 0 
            ? globalConfig.whitelist.map(id => `├ ${id}`).join('\n')
            : '├ Kosong';
        return `✅ *WHITELIST*\n${list}\n\nTotal: ${globalConfig.whitelist.length} grup`;
    }
    
    if (action === 'clear') {
        globalConfig.whitelist = [];
        await saveAllData();
        return "✅ Whitelist cleared! Semua grup diblokir kecuali ada di auto-approve.";
    }
    
    if (ids.length === 0) {
        return `❌ Butuh chat IDs! Contoh: /super whitelist add 123456789`;
    }
    
    for (const id of ids) {
        if (action === 'add') {
            if (!globalConfig.whitelist.includes(id)) {
                globalConfig.whitelist.push(id);
                
                // Auto create group data if not exists
                if (!groupsData[id]) {
                    groupsData[id] = createNewGroupData(id, {
                        name: `Group ${id}`,
                        enabled: true
                    });
                    log('super', `Auto-created group for whitelist: ${id}`);
                }
            }
        } else if (action === 'remove') {
            const index = globalConfig.whitelist.indexOf(id);
            if (index > -1) {
                globalConfig.whitelist.splice(index, 1);
            }
        }
    }
    
    await saveAllData();
    
    return `✅ Whitelist ${action === 'add' ? 'ditambah' : 'dihapus'} ${ids.length} ID!`;
}

async function manageBlacklist(params, chatId) {
    const [action, ...ids] = params;
    
    if (!action || !['add', 'remove', 'list', 'clear'].includes(action)) {
        return "❌ Format: /super blacklist [add/remove/list/clear] [chat_id...]";
    }
    
    if (action === 'list') {
        const list = globalConfig.blacklist.length > 0 
            ? globalConfig.blacklist.map(id => `├ ${id}`).join('\n')
            : '├ Kosong';
        return `✅ *BLACKLIST*\n${list}\n\nTotal: ${globalConfig.blacklist.length} grup`;
    }
    
    if (action === 'clear') {
        globalConfig.blacklist = [];
        await saveAllData();
        return "✅ Blacklist cleared!";
    }
    
    if (ids.length === 0) {
        return `❌ Butuh chat IDs!`;
    }
    
    for (const id of ids) {
        if (action === 'add') {
            if (!globalConfig.blacklist.includes(id)) {
                globalConfig.blacklist.push(id);
            }
        } else if (action === 'remove') {
            const index = globalConfig.blacklist.indexOf(id);
            if (index > -1) {
                globalConfig.blacklist.splice(index, 1);
            }
        }
    }
    
    await saveAllData();
    
    return `✅ Blacklist ${action === 'add' ? 'ditambah' : 'dihapus'} ${ids.length} ID!`;
}

async function toggleAutoApprove(params) {
    const action = params[0];
    
    if (!action || !['on', 'off', 'status'].includes(action)) {
        return "❌ Format: /super autoapprove [on/off/status]";
    }
    
    if (action === 'status') {
        return `✅ Auto Approve: ${globalConfig.autoApprove ? 'ON' : 'OFF'}\nWhitelist: ${globalConfig.whitelist.length} grup\nBlacklist: ${globalConfig.blacklist.length} grup`;
    }
    
    globalConfig.autoApprove = action === 'on';
    await saveAllData();
    
    return `✅ Auto Approve: ${globalConfig.autoApprove ? 'ON' : 'OFF'}`;
}

async function broadcastMessage(params) {
    const message = params.join(' ');
    
    if (!message || message.length < 3) {
        return "❌ Butuh pesan untuk broadcast! Minimal 3 karakter.";
    }
    
    let sent = 0;
    let failed = 0;
    const failedGroups = [];
    
    for (const [chatId, groupData] of Object.entries(groupsData)) {
        if (groupData.enabled) {
            try {
                await bot.sendMessage(chatId, 
                    `📢 *BROADCAST FROM SUPER ADMIN*\n\n${message}\n\n_Message sent to all active groups_`,
                    { parse_mode: 'Markdown' }
                );
                sent++;
                log('broadcast', `Sent to ${chatId} - ${groupData.name}`);
            } catch (error) {
                failed++;
                failedGroups.push(`${chatId}: ${error.message}`);
                log('error', `Broadcast failed for ${chatId}: ${error.message}`);
            }
        }
    }
    
    let result = `📢 *Broadcast Report*\n\n`;
    result += `✅ Sent: ${sent} groups\n`;
    result += `❌ Failed: ${failed} groups\n`;
    
    if (failed > 0 && failedGroups.length > 0) {
        result += `\nFailed groups:\n`;
        failedGroups.slice(0, 5).forEach(group => {
            result += `• ${group}\n`;
        });
        if (failedGroups.length > 5) {
            result += `...dan ${failedGroups.length - 5} lainnya`;
        }
    }
    
    return result;
}

async function showGroupStatus(params, chatId) {
    const targetChatId = params[0] || chatId.toString();
    
    const groupData = groupsData[targetChatId];
    const inWhitelist = globalConfig.whitelist.includes(targetChatId);
    const inBlacklist = globalConfig.blacklist.includes(targetChatId);
    const isAllowed = isGroupAllowed(parseInt(targetChatId));
    
    let status = `📊 *STATUS GRUP*\n\n`;
    status += `📍 ID: ${targetChatId}\n`;
    status += `📝 Nama: ${groupData?.name || 'Tidak ditemukan'}\n`;
    status += `🔒 Whitelist: ${inWhitelist ? '✅' : '❌'}\n`;
    status += `🚫 Blacklist: ${inBlacklist ? '✅' : '❌'}\n`;
    status += `⚡ Auto Approve: ${globalConfig.autoApprove ? 'ON' : 'OFF'}\n`;
    status += `🎯 Status: ${isAllowed ? '✅ DIJINKAN' : '❌ DIBLOKIR'}\n`;
    status += `🤖 Bot Active: ${groupData?.enabled ? '✅' : '❌'}\n`;
    status += `💬 Chat Feature: ${groupData?.config?.enableChat !== false ? '✅' : '❌'}\n\n`;
    
    if (groupData) {
        const wallet = groupData.memory.wallet || { IDR: 0, USD: 0 };
        const rate = groupData.memory.exchangeRate || CONFIG.DEFAULT_RATE;
        const totalWorth = wallet.IDR + (wallet.USD * rate);
        
        status += `💰 Financial:\n`;
        status += `├ IDR: Rp ${wallet.IDR.toLocaleString('id-ID')}\n`;
        status += `├ USD: $${wallet.USD.toFixed(2)}\n`;
        status += `├ Total: Rp ${totalWorth.toLocaleString('id-ID')}\n`;
        status += `├ Users: ${Object.keys(groupData.users || {}).length}\n`;
        status += `└ Txns: ${groupData.memory.statistics?.totalTransactions || 0}\n\n`;
    }
    
    if (!isAllowed) {
        status += `*Untuk mengaktifkan:*\n`;
        status += `/super whitelist add ${targetChatId}\n`;
        status += `atau\n`;
        status += `/super autoapprove on\n`;
    }
    
    return status;
}

async function fixGroup(params, chatId) {
    const targetChatId = params[0] || chatId.toString();
    
    if (!groupsData[targetChatId]) {
        return `❌ Grup ${targetChatId} tidak ditemukan!`;
    }
    
    const groupData = groupsData[targetChatId];
    
    // Fix config jika ada masalah
    ensureGroupConfigComplete(groupData);
    
    // Pastikan enableChat true
    groupData.config.enableChat = true;
    
    // Pastikan grup enabled
    groupData.enabled = true;
    
    // Tambah ke whitelist jika belum
    if (!globalConfig.whitelist.includes(targetChatId)) {
        globalConfig.whitelist.push(targetChatId);
    }
    
    // Hapus dari blacklist jika ada
    const blacklistIndex = globalConfig.blacklist.indexOf(targetChatId);
    if (blacklistIndex > -1) {
        globalConfig.blacklist.splice(blacklistIndex, 1);
    }
    
    await saveAllData();
    
    // Kirim welcome message ulang
    try {
        await bot.sendMessage(targetChatId,
            `🔧 *GRUP DIPERBAIKI!*\n\n` +
            `Semua masalah telah diperbaiki:\n` +
            `✅ Bot diaktifkan\n` +
            `✅ Chat feature diaktifkan\n` +
            `✅ Ditambahkan ke whitelist\n` +
            `✅ Config diperbarui\n\n` +
            `Sekarang bot siap digunakan! 🚀`,
            {
                parse_mode: 'Markdown',
                reply_markup: getGroupKeyboard(parseInt(targetChatId), targetChatId).reply_markup
            }
        );
    } catch (error) {
        log('error', `Failed to send fix message: ${error.message}`);
    }
    
    return `✅ Grup ${targetChatId} (${groupData.name}) telah diperbaiki!\n\n` +
           `✅ Enabled: ${groupData.enabled}\n` +
           `✅ Enable Chat: ${groupData.config.enableChat}\n` +
           `✅ In Whitelist: ${globalConfig.whitelist.includes(targetChatId)}\n` +
           `✅ Not in Blacklist: ${!globalConfig.blacklist.includes(targetChatId)}`;
}

async function createBackup(chatId) {
    try {
        const timestamp = moment().format('YYYYMMDD_HHmmss');
        const backupDir = path.join(CONFIG.DATA_DIR, 'backups');
        await fs.mkdir(backupDir, { recursive: true });
        
        const backupPath = path.join(backupDir, `backup_${timestamp}.json`);
        const backupData = {
            timestamp: new Date().toISOString(),
            groups: groupsData,
            globalConfig: globalConfig
        };
        
        await fs.writeFile(backupPath, JSON.stringify(backupData, null, 2));
        
        return `✅ Backup created: backup_${timestamp}.json\n\n` +
               `Total Groups: ${Object.keys(groupsData).length}\n` +
               `File saved to: ${backupPath}`;
    } catch (error) {
        log('error', `Backup failed: ${error.message}`);
        return `❌ Backup failed: ${error.message}`;
    }
}

async function deleteGroup(params, chatId) {
    const targetChatId = params[0];
    
    if (!targetChatId) {
        return "❌ Butuh chat ID! Contoh: /super delete -100123456789";
    }
    
    if (!groupsData[targetChatId]) {
        return `❌ Grup ${targetChatId} tidak ditemukan!`;
    }
    
    const groupName = groupsData[targetChatId].name;
    
    // Hapus dari semua list
    delete groupsData[targetChatId];
    
    const whitelistIndex = globalConfig.whitelist.indexOf(targetChatId);
    if (whitelistIndex > -1) {
        globalConfig.whitelist.splice(whitelistIndex, 1);
    }
    
    const blacklistIndex = globalConfig.blacklist.indexOf(targetChatId);
    if (blacklistIndex > -1) {
        globalConfig.blacklist.splice(blacklistIndex, 1);
    }
    
    // Hapus file data
    try {
        const groupPath = path.join(CONFIG.DATA_DIR, 'groups', `${targetChatId}.json`);
        await fs.unlink(groupPath).catch(() => {});
    } catch (error) {
        // Ignore file deletion errors
    }
    
    await saveAllData();
    
    return `✅ Grup ${groupName} (${targetChatId}) berhasil dihapus!\n\n` +
           `✅ Data dihapus dari memory\n` +
           `✅ Dihapus dari whitelist/blacklist\n` +
           `✅ File data dihapus`;
}

// ================= MESSAGE HANDLER =================
bot.on('message', async (msg) => {
    if (!msg.chat) return;
    
    const chatId = msg.chat.id;
    const userId = msg.from.id;
    const userName = msg.from.first_name || 'User';
    const text = msg.text ? msg.text.trim() : '';
    const chatType = msg.chat.type;
    
    const messageId = `${chatId}_${msg.message_id}`;
    
    // Prevent duplicate processing
    if (processingMessages.has(messageId)) {
        return;
    }
    processingMessages.add(messageId);
    
    log('info', `Message received`, {
        chatId,
        userId,
        userName,
        chatType,
        text: text.substring(0, 100)
    });
    
    try {
        // Handle private chat
        if (chatType === 'private') {
            if (text.startsWith('/')) {
                await bot.sendMessage(chatId, 
                    "🤖 *Finance Bot*\n\n" +
                    "Bot ini cuma bisa dipake di grup ya bro!\n" +
                    "Add aku ke grup lu, lalu atur admin pake /super (kalo lu super admin).\n\n" +
                    `Super Admin IDs: ${CONFIG.SUPER_ADMIN_IDS.join(', ')}`,
                    { parse_mode: 'Markdown' }
                );
            }
            processingMessages.delete(messageId);
            return;
        }
        
        // Handle super admin commands even if group not allowed
        if (text.startsWith('/super')) {
            const isSuperAdmin = CONFIG.SUPER_ADMIN_IDS.includes(parseInt(userId));
            if (isSuperAdmin) {
                await bot.sendChatAction(chatId, 'typing');
                const args = text.split(' ').slice(1);
                
                if (args.length === 0 || args[0] === 'panel') {
                    const result = await showSuperAdminPanel(chatId);
                    await bot.sendMessage(chatId, result.text, { 
                        parse_mode: 'Markdown',
                        reply_markup: result.keyboard.reply_markup
                    });
                } else {
                    const response = await handleSuperAdminCommand(args, chatId);
                    if (typeof response === 'object' && response.text) {
                        await bot.sendMessage(chatId, response.text, { 
                            parse_mode: 'Markdown',
                            reply_markup: response.keyboard?.reply_markup || getGroupKeyboard(chatId, userId).reply_markup
                        });
                    } else {
                        await bot.sendMessage(chatId, response, { 
                            parse_mode: 'Markdown',
                            reply_markup: getGroupKeyboard(chatId, userId).reply_markup
                        });
                    }
                }
                processingMessages.delete(messageId);
                return;
            }
        }
        
        // Cek apakah grup diizinkan
        if (!isGroupAllowed(chatId)) {
            log('warning', `Group ${chatId} not allowed`);
            
            // Only show message for super admins
            const isSuperAdmin = CONFIG.SUPER_ADMIN_IDS.includes(parseInt(userId));
            if (isSuperAdmin && text) {
                await bot.sendMessage(chatId,
                    `⚠️ *Grup Belum Diapprove!*\n\n` +
                    `Grup: ${msg.chat.title || 'Unknown Group'}\n` +
                    `Grup ID: ${chatId}\n` +
                    `Status: ${globalConfig.blacklist.includes(chatId.toString()) ? 'BLACKLISTED' : 'NOT IN WHITELIST'}\n\n` +
                    `Whitelist: ${globalConfig.whitelist.length} grup\n` +
                    `Auto Approve: ${globalConfig.autoApprove ? 'ON' : 'OFF'}\n\n` +
                    `Gunakan salah satu:\n` +
                    `/super whitelist add ${chatId}\n` +
                    `atau\n` +
                    `/super autoapprove on\n\n` +
                    `Setelah itu, kirim pesan apa saja untuk memulai.`,
                    { 
                        parse_mode: 'Markdown',
                        reply_markup: {
                            remove_keyboard: true
                        }
                    }
                );
            }
            processingMessages.delete(messageId);
            return;
        }
        
        // Ambil atau buat data grup
        let groupData = getGroupData(chatId);
        if (!groupData) {
            // Grup tidak ada dan tidak diizinkan auto-create
            // Cek lagi apakah seharusnya diizinkan
            const shouldExist = !globalConfig.blacklist.includes(chatId.toString()) && 
                               (globalConfig.autoApprove || globalConfig.whitelist.includes(chatId.toString()));
            
            if (!shouldExist) {
                // Grup tidak diizinkan
                processingMessages.delete(messageId);
                return;
            }
            
            // Buat grup baru
            const groupName = msg.chat.title || `Group ${chatId}`;
            groupData = createNewGroupData(chatId.toString(), {
                name: groupName,
                enabled: true
            });
            groupsData[chatId.toString()] = groupData;
            
            // Tambah ke whitelist jika auto-approve
            if (globalConfig.autoApprove && !globalConfig.whitelist.includes(chatId.toString())) {
                globalConfig.whitelist.push(chatId.toString());
            }
            
            // Simpan data
            await saveAllData();
            
            log('group', `Created new group: ${chatId} - ${groupName}`);
            
            // Kirim welcome message untuk grup baru
            const welcomeMsg = `🤖 *FINANCE BOT - WELCOME!*\n\n` +
                              `Halo ${groupName}! 👋\n\n` +
                              `Finance Bot otomatis aktif di grup ini! 🎉\n\n` +
                              `*Fitur yang tersedia:*\n` +
                              `💰 Catat pemasukan/pengeluaran\n` +
                              `📊 Pantau limit harian/bulanan\n` +
                              `💱 Konversi USD/IDR\n` +
                              `👑 Admin panel untuk kontrol\n\n` +
                              `*Cara pakai:*\n` +
                              `• "gajian 5 juta"\n` +
                              `• "makan 75rb"\n` +
                              `• "rate 16000"\n` +
                              `• "cek saldo"\n` +
                              `• Tombol di bawah 👇\n\n` +
                              `Selamat menggunakan! 🚀`;
            
            await bot.sendMessage(chatId, welcomeMsg, {
                parse_mode: 'Markdown',
                reply_markup: getGroupKeyboard(chatId, userId).reply_markup
            });
            
            // Setelah welcome message, tidak perlu proses pesan pertama
            processingMessages.delete(messageId);
            return;
        }
        
        // Update group info if needed
        if (!groupData.name || groupData.name === `Group ${chatId}`) {
            groupData.name = msg.chat.title || `Group ${chatId}`;
            await saveAllData();
        }
        
        // Handle empty messages
        if (!text || text.length < 1) {
            processingMessages.delete(messageId);
            return;
        }
        
        // Handle admin commands (always allowed for admins, even if bot disabled)
        if (text.startsWith('/')) {
            const [command, ...args] = text.split(' ');
            
            // Check if it's an admin command
            const adminCommands = ['/config', '/setlimit', '/addadmin', '/removeadmin', 
                                 '/enable', '/disable', '/reset', '/stats', '/users', 
                                 '/approve', '/super', '/enablechat', '/disablechat', '/transactions'];
            
            if (adminCommands.some(cmd => text.startsWith(cmd))) {
                await bot.sendChatAction(chatId, 'typing');
                const response = await handleAdminCommand(chatId, userId, command, args);
                await bot.sendMessage(chatId, response, { 
                    parse_mode: 'Markdown',
                    reply_markup: getGroupKeyboard(chatId, userId).reply_markup
                });
                processingMessages.delete(messageId);
                return;
            }
        }
        
        // Check if bot is enabled in this group (for non-admin messages)
        if (!isBotEnabledInGroup(chatId)) {
            const isAdmin = isUserAdmin(chatId, userId);
            if (isAdmin) {
                await bot.sendMessage(chatId,
                    `⚠️ *Bot Nonaktif!*\n\n` +
                    `Bot saat ini dinonaktifkan di grup ini.\n` +
                    `Gunakan /enable untuk mengaktifkan kembali.`,
                    { 
                        parse_mode: 'Markdown',
                        reply_markup: getGroupKeyboard(chatId, userId).reply_markup
                    }
                );
            }
            processingMessages.delete(messageId);
            return;
        }
        
        // Handle button commands
        const buttonResponses = {
            '💰 Saldo': async () => {
                await bot.sendChatAction(chatId, 'typing');
                const result = handleBalanceInfo(groupData);
                await bot.sendMessage(chatId, result.message, { 
                    parse_mode: 'Markdown',
                    reply_markup: getGroupKeyboard(chatId, userId).reply_markup
                });
            },
            
            '📊 Harian': async () => {
                await bot.sendChatAction(chatId, 'typing');
                const result = handleHistoryInfo(groupData);
                await bot.sendMessage(chatId, result.message, {
                    parse_mode: 'Markdown',
                    reply_markup: getGroupKeyboard(chatId, userId).reply_markup
                });
            },
            
            '📅 Bulanan': async () => {
                await bot.sendChatAction(chatId, 'typing');
                const result = handleMonthlyInfo(groupData);
                await bot.sendMessage(chatId, result.message, {
                    parse_mode: 'Markdown',
                    reply_markup: getGroupKeyboard(chatId, userId).reply_markup
                });
            },
            
            '🔄 Koreksi': async () => {
                await bot.sendChatAction(chatId, 'typing');
                const aiData = {
                    type: "finance",
                    action: "cancel",
                    message: "🔄 Transaksi terakhir berhasil dibatalin!"
                };
                
                const result = await executeAction(aiData, groupData, 
                    { id: userId, name: userName }, chatId);
                
                await bot.sendMessage(chatId, result.message, {
                    parse_mode: 'Markdown',
                    reply_markup: getGroupKeyboard(chatId, userId).reply_markup
                });
            },
            
            '❓ Bantuan': async () => {
                await bot.sendChatAction(chatId, 'typing');
                const result = handleHelpInfo(groupData, userId);
                await bot.sendMessage(chatId, result.message, {
                    parse_mode: 'Markdown',
                    reply_markup: getGroupKeyboard(chatId, userId).reply_markup
                });
            },
            
            '💱 Rate': async () => {
                await bot.sendChatAction(chatId, 'typing');
                const currentRate = groupData.memory.exchangeRate || CONFIG.DEFAULT_RATE;
                await bot.sendMessage(chatId,
                    `💱 *Rate Saat Ini:*\n` +
                    `1 USD = Rp ${currentRate.toLocaleString('id-ID')}\n\n` +
                    `Untuk update rate, ketik:\n` +
                    `"rate 16000" atau "update rate 15500"`,
                    {
                        parse_mode: 'Markdown',
                        reply_markup: getGroupKeyboard(chatId, userId).reply_markup
                    }
                );
            },
            
            '📈 Stats': async () => {
                await bot.sendChatAction(chatId, 'typing');
                const result = showGroupStats(groupData);
                await bot.sendMessage(chatId, result, {
                    parse_mode: 'Markdown',
                    reply_markup: getGroupKeyboard(chatId, userId).reply_markup
                });
            },
            
            '⚙️ Config': async () => {
                const isAdmin = isUserAdmin(chatId, userId);
                if (!isAdmin) {
                    await bot.sendMessage(chatId, 
                        "⛔ Hanya admin yang bisa akses menu ini!",
                        { 
                            parse_mode: 'Markdown',
                            reply_markup: getGroupKeyboard(chatId, userId).reply_markup
                        }
                    );
                    return;
                }
                
                await bot.sendChatAction(chatId, 'typing');
                const result = showGroupConfig(groupData);
                await bot.sendMessage(chatId, result, {
                    parse_mode: 'Markdown',
                    reply_markup: getGroupKeyboard(chatId, userId).reply_markup
                });
            },
            
            '👥 Users': async () => {
                const isAdmin = isUserAdmin(chatId, userId);
                if (!isAdmin) {
                    await bot.sendMessage(chatId, 
                        "⛔ Hanya admin yang bisa akses menu ini!",
                        { 
                            parse_mode: 'Markdown',
                            reply_markup: getGroupKeyboard(chatId, userId).reply_markup
                        }
                    );
                    return;
                }
                
                await bot.sendChatAction(chatId, 'typing');
                const result = showGroupUsers(groupData);
                await bot.sendMessage(chatId, result, {
                    parse_mode: 'Markdown',
                    reply_markup: getGroupKeyboard(chatId, userId).reply_markup
                });
            },
            
            '📋 Transaksi': async () => {
                const isAdmin = isUserAdmin(chatId, userId);
                if (!isAdmin) {
                    await bot.sendMessage(chatId, 
                        "⛔ Hanya admin yang bisa akses menu ini!",
                        { 
                            parse_mode: 'Markdown',
                            reply_markup: getGroupKeyboard(chatId, userId).reply_markup
                        }
                    );
                    return;
                }
                
                await bot.sendChatAction(chatId, 'typing');
                const result = await showTransactions(chatId, [], groupData, userId);
                await bot.sendMessage(chatId, result, {
                    parse_mode: 'Markdown',
                    reply_markup: getGroupKeyboard(chatId, userId).reply_markup
                });
            },
            
            '👑 Admin Panel': async () => {
                const isAdmin = isUserAdmin(chatId, userId);
                if (!isAdmin) {
                    await bot.sendMessage(chatId, 
                        "⛔ Hanya admin yang bisa akses menu ini!",
                        { 
                            parse_mode: 'Markdown',
                            reply_markup: getGroupKeyboard(chatId, userId).reply_markup
                        }
                    );
                    return;
                }
                
                const adminText = `👑 *ADMIN PANEL ${groupData.name}*\n\n` +
                                 `*📋 Quick Commands:*\n` +
                                 `• /config - Pengaturan grup\n` +
                                 `• /setlimit [harian] [bulanan] - Atur limit\n` +
                                 `• /addadmin [user_id] - Tambah admin\n` +
                                 `• /removeadmin [user_id] - Hapus admin\n` +
                                 `• /enablechat - Aktifkan chat\n` +
                                 `• /disablechat - Nonaktifkan chat\n` +
                                 `• /stats - Statistik grup\n` +
                                 `• /users - Daftar user\n` +
                                 `• /transactions - List transaksi\n` +
                                 `• /approve - Approve transaksi\n` +
                                 `• /enable - Aktifkan bot\n` +
                                 `• /disable - Nonaktifkan bot\n` +
                                 `• /reset [type] - Reset data\n\n` +
                                 `*💡 Tips:*\n` +
                                 `Gunakan tombol di bawah untuk akses cepat!`;
                
                await bot.sendMessage(chatId, adminText, {
                    parse_mode: 'Markdown',
                    reply_markup: getGroupKeyboard(chatId, userId).reply_markup
                });
            },
            
            '👑👑 Super Admin': async () => {
                const isSuperAdmin = CONFIG.SUPER_ADMIN_IDS.includes(parseInt(userId));
                if (!isSuperAdmin) {
                    await bot.sendMessage(chatId, 
                        "⛔ Hanya SUPER ADMIN yang bisa akses menu ini!",
                        { 
                            parse_mode: 'Markdown',
                            reply_markup: getGroupKeyboard(chatId, userId).reply_markup
                        }
                    );
                    return;
                }
                
                await bot.sendChatAction(chatId, 'typing');
                const result = await showSuperAdminPanel(chatId);
                await bot.sendMessage(chatId, result.text, {
                    parse_mode: 'Markdown',
                    reply_markup: result.keyboard.reply_markup
                });
            }
        };
        
        if (buttonResponses[text]) {
            await buttonResponses[text]();
            processingMessages.delete(messageId);
            return;
        }
        
        // Check if chat is enabled - PERBAIKAN DI SINI
        const enableChat = groupData.config.enableChat !== false; // default true jika tidak di-set
        
        // Daftar semua tombol yang valid
        const validButtons = [
            '💰 Saldo', '📊 Harian', '📅 Bulanan', '🔄 Koreksi', '❓ Bantuan',
            '💱 Rate', '📈 Stats', '⚙️ Config', '👥 Users', '📋 Transaksi',
            '👑 Admin Panel', '👑👑 Super Admin'
        ];
        
        const isButtonCommand = validButtons.includes(text);
        const isCommand = text.startsWith('/');
        
        if (!enableChat && !isCommand && !isButtonCommand) {
            // Hanya nonaktifkan chat biasa, tapi tetap izinkan command & tombol
            log('debug', `Chat feature disabled for non-command messages`, { text: text.substring(0, 50) });
            
            // Beri tahu user kalau chat dinonaktifkan
            await bot.sendMessage(chatId,
                "ℹ️ *Fitur chat dinonaktifkan di grup ini.*\n\n" +
                "Silakan gunakan:\n" +
                "• Tombol di bawah keyboard\n" +
                "• Command dengan / (contoh: /config)\n" +
                "• Atau minta admin aktifkan dengan /enablechat",
                {
                    parse_mode: 'Markdown',
                    reply_markup: getGroupKeyboard(chatId, userId).reply_markup
                }
            );
            
            processingMessages.delete(messageId);
            return;
        }
        
        // Handle other messages with AI
        const isAdmin = isUserAdmin(chatId, userId);
        const aiData = await askAI(text, userName, groupData, isAdmin);
        
        if (aiData.error) {
            await bot.sendMessage(chatId, aiData.message, {
                parse_mode: 'Markdown',
                reply_markup: getGroupKeyboard(chatId, userId).reply_markup
            });
            processingMessages.delete(messageId);
            return;
        }
        
        // Handle chat responses immediately
        if (aiData.type === 'chat') {
            await bot.sendMessage(chatId, aiData.chat_response || aiData.message, {
                parse_mode: 'Markdown',
                reply_markup: getGroupKeyboard(chatId, userId).reply_markup
            });
            processingMessages.delete(messageId);
            return;
        }
        
        // Handle info responses
        if (aiData.type === 'info') {
            await bot.sendMessage(chatId, aiData.message, {
                parse_mode: 'Markdown',
                reply_markup: getGroupKeyboard(chatId, userId).reply_markup
            });
            processingMessages.delete(messageId);
            return;
        }
        
        // Handle confirmation for finance actions
        if (aiData.requires_confirm || aiData.warning_level === 'danger' || aiData.warning_level === 'extreme') {
            const confirmId = `confirm_${Date.now()}_${userId}_${chatId}`;
            const confirmKeyboard = {
                inline_keyboard: [[
                    { 
                        text: aiData.warning_level === 'extreme' ? '💀 LANJUT BOROS!' : '✅ Gas! Lanjutin', 
                        callback_data: `${confirmId}_yes` 
                    },
                    { 
                        text: aiData.warning_level === 'extreme' ? '😱 GUA TAKUT!' : '❌ Gak jadi', 
                        callback_data: `${confirmId}_no` 
                    }
                ]]
            };
            
            let confirmMsg = `🔄 *KONFIRMASI ${aiData.warning_level === 'extreme' ? 'BOROS' : 'STANDAR'}!*\n\n${aiData.message}`;
            if (aiData.warning_message) {
                confirmMsg += `\n\n${aiData.warning_message}`;
            }
            
            // Add extra roasting for extreme cases
            if (aiData.warning_level === 'extreme') {
                confirmMsg += `\n\n💀 *SERIUS NIH MAU LANJUT?*\nLimit udah lewat 150% bro, beneran mau tambah lagi?`;
            } else if (aiData.warning_level === 'danger') {
                confirmMsg += `\n\n⚠️ *YAKIN MAU LANJUT?*\nUdah lewat limit nih, masih mau nambah?`;
            }
            
            confirmMsg += `\n\n*Lanjutin gak nih?*`;
            
            await bot.sendMessage(chatId, confirmMsg, {
                parse_mode: 'Markdown',
                reply_markup: confirmKeyboard
            });
            
            // Store pending confirmation
            pendingConfirmations[confirmId] = {
                chatId,
                userId,
                userName,
                aiData,
                timestamp: Date.now(),
                groupData: JSON.parse(JSON.stringify(groupData))
            };
            
            setTimeout(() => {
                if (pendingConfirmations[confirmId]) {
                    delete pendingConfirmations[confirmId];
                }
            }, 60000);
            
            processingMessages.delete(messageId);
            return;
        }
        
        // Execute action immediately
        const result = await executeAction(aiData, groupData, 
            { id: userId, name: userName }, chatId);
        
        let response = result.message;
        
        // Add status if it's a finance action
        if (result.success && result.type === 'finance' && !result.infoOnly) {
            const wallet = groupData.memory.wallet || { IDR: 0, USD: 0 };
            const dailyUSD = groupData.memory.dailySpent?.USD || 0;
            const dailyLimit = groupData.config.dailyLimit || CONFIG.DEFAULT_DAILY_LIMIT;
            const dailyPercent = dailyLimit > 0 ? (dailyUSD / dailyLimit) * 100 : 0;
            
            const monthlyUSD = groupData.memory.monthlySpent?.USD || 0;
            const monthlyLimit = groupData.config.monthlyLimit || CONFIG.DEFAULT_MONTHLY_LIMIT;
            const monthlyPercent = monthlyLimit > 0 ? (monthlyUSD / monthlyLimit) * 100 : 0;
            
            response += `\n\n━━━━━━━━━━━━━━━━━━━━`;
            response += `\n💰 Saldo: Rp ${wallet.IDR.toLocaleString('id-ID')} | $${wallet.USD.toFixed(2)}`;
            response += `\n🍽️ Harian: $${dailyUSD.toFixed(2)}/${dailyLimit} (${dailyPercent.toFixed(0)}%)`;
            response += `\n📅 Bulanan: $${monthlyUSD.toFixed(2)}/${monthlyLimit} (${monthlyPercent.toFixed(0)}%)`;
        }
        
        // SELALU gunakan keyboard untuk semua response
        await bot.sendMessage(chatId, response, {
            parse_mode: 'Markdown',
            reply_markup: getGroupKeyboard(chatId, userId).reply_markup
        });
        
        log('success', `Processed: ${aiData.type} - ${aiData.action}`, {
            chatId,
            user: userName,
            success: result.success
        });
        
    } catch (error) {
        log('error', `Handler error: ${error.message}`, error.stack);
        await bot.sendMessage(chatId,
            `❌ Waduh error nih: ${error.message}\nCoba lagi ya bro!`,
            { 
                parse_mode: 'Markdown',
                reply_markup: getGroupKeyboard(chatId, userId).reply_markup
            }
        );
    } finally {
        processingMessages.delete(messageId);
    }
});

// ================= CALLBACK QUERY HANDLER =================
bot.on('callback_query', async (callbackQuery) => {
    const chatId = callbackQuery.message.chat.id;
    const userId = callbackQuery.from.id;
    const data = callbackQuery.data;
    const messageId = callbackQuery.message.message_id;
    
    try {
        await bot.answerCallbackQuery(callbackQuery.id);
        
        // Handle confirmation callbacks
        if (data.includes('_yes') || data.includes('_no')) {
            const baseId = data.substring(0, data.lastIndexOf('_'));
            const action = data.endsWith('_yes') ? 'confirm' : 'cancel';
            
            const pending = pendingConfirmations[baseId];
            
            if (!pending) {
                await bot.sendMessage(chatId, "❌ Konfirmasi udah kadaluarsa bro!");
                return;
            }
            
            if (pending.userId !== userId) {
                await bot.sendMessage(chatId, "❌ Ini bukan konfirmasi lu bro!");
                return;
            }
            
            delete pendingConfirmations[baseId];
            
            if (action === 'cancel') {
                await bot.editMessageText(
                    "❌ *Gak jadi deh!* Transaksi dibatalin.",
                    { chat_id: chatId, message_id: messageId, parse_mode: 'Markdown' }
                );
                return;
            }
            
            // Get current group data
            const groupData = getGroupData(chatId);
            if (!groupData) {
                await bot.editMessageText(
                    "❌ Group data not found!",
                    { chat_id: chatId, message_id: messageId }
                );
                return;
            }
            
            // Execute the action
            const result = await executeAction(pending.aiData, groupData,
                { id: userId, name: pending.userName }, chatId);
            
            let response = `✅ *DILANJUTIN!*\n\n${result.message}`;
            
            if (result.success && result.type === 'finance' && !result.infoOnly) {
                const wallet = groupData.memory.wallet || { IDR: 0, USD: 0 };
                const dailyUSD = groupData.memory.dailySpent?.USD || 0;
                const dailyLimit = groupData.config.dailyLimit || CONFIG.DEFAULT_DAILY_LIMIT;
                const dailyPercent = dailyLimit > 0 ? (dailyUSD / dailyLimit) * 100 : 0;
                
                const monthlyUSD = groupData.memory.monthlySpent?.USD || 0;
                const monthlyLimit = groupData.config.monthlyLimit || CONFIG.DEFAULT_MONTHLY_LIMIT;
                const monthlyPercent = monthlyLimit > 0 ? (monthlyUSD / monthlyLimit) * 100 : 0;
                
                response += `\n\n━━━━━━━━━━━━━━━━━━━━`;
                response += `\n💰 Saldo: Rp ${wallet.IDR.toLocaleString('id-ID')} | $${wallet.USD.toFixed(2)}`;
                response += `\n🍽️ Harian: $${dailyUSD.toFixed(2)}/${dailyLimit} (${dailyPercent.toFixed(0)}%)`;
                response += `\n📅 Bulanan: $${monthlyUSD.toFixed(2)}/${monthlyLimit} (${monthlyPercent.toFixed(0)}%)`;
            }
            
            await bot.editMessageText(response, {
                chat_id: chatId,
                message_id: messageId,
                parse_mode: 'Markdown'
            });
            
            log('success', `Confirmed transaction`, {
                chatId,
                userId,
                action: pending.aiData.action
            });
        }
        
        // Handle super admin panel callbacks
        else if (data.startsWith('super_')) {
            const isSuperAdmin = CONFIG.SUPER_ADMIN_IDS.includes(parseInt(userId));
            if (!isSuperAdmin) {
                await bot.sendMessage(chatId, "⛔ Hanya Super Admin yang bisa akses panel ini!");
                return;
            }
            
            const action = data.replace('super_', '');
            
            switch (action) {
                case 'panel':
                    const panel = await showSuperAdminPanel(chatId);
                    await bot.editMessageText(panel.text, {
                        chat_id: chatId,
                        message_id: messageId,
                        parse_mode: 'Markdown',
                        reply_markup: panel.keyboard.reply_markup
                    });
                    break;
                    
                case 'listgroups':
                    const list = await showAllGroupsPanel(chatId);
                    await bot.editMessageText(list.text, {
                        chat_id: chatId,
                        message_id: messageId,
                        parse_mode: 'Markdown',
                        reply_markup: list.keyboard.reply_markup
                    });
                    break;
                    
                case 'config':
                    const configText = `⚙️ *GLOBAL CONFIG*\n\n` +
                                     `Whitelist: ${globalConfig.whitelist.length} groups\n` +
                                     `Blacklist: ${globalConfig.blacklist.length} groups\n` +
                                     `Auto Approve: ${globalConfig.autoApprove ? '✅ ON' : '❌ OFF'}\n\n` +
                                     `*Commands:*\n` +
                                     `/super whitelist list\n` +
                                     `/super blacklist list\n` +
                                     `/super autoapprove [on/off]`;
                    
                    await bot.editMessageText(configText, {
                        chat_id: chatId,
                        message_id: messageId,
                        parse_mode: 'Markdown',
                        reply_markup: {
                            inline_keyboard: [
                                [
                                    { text: '🔙 Back', callback_data: 'super_panel' },
                                    { text: '🔄 Refresh', callback_data: 'super_config' }
                                ]
                            ]
                        }
                    });
                    break;
                    
                case 'stats':
                    const totalGroups = Object.keys(groupsData).length;
                    const activeGroups = Object.values(groupsData).filter(g => g.enabled).length;
                    const totalUsers = Object.values(groupsData).reduce((sum, g) => sum + Object.keys(g.users || {}).length, 0);
                    const totalTransactions = Object.values(groupsData).reduce((sum, g) => sum + (g.memory?.statistics?.totalTransactions || 0), 0);
                    const totalWorth = Object.values(groupsData).reduce((sum, g) => {
                        const wallet = g.memory.wallet || { IDR: 0, USD: 0 };
                        const rate = g.memory.exchangeRate || CONFIG.DEFAULT_RATE;
                        return sum + wallet.IDR + (wallet.USD * rate);
                    }, 0);
                    
                    const statsText = `📊 *GLOBAL STATISTICS*\n\n` +
                                    `• Total Groups: ${totalGroups}\n` +
                                    `• Active Groups: ${activeGroups}\n` +
                                    `• Total Users: ${totalUsers}\n` +
                                    `• Total Transactions: ${totalTransactions}\n` +
                                    `• Total Worth: Rp ${totalWorth.toLocaleString('id-ID')}\n` +
                                    `• Whitelist Groups: ${globalConfig.whitelist.length}\n` +
                                    `• Blacklist Groups: ${globalConfig.blacklist.length}\n` +
                                    `• Auto Approve: ${globalConfig.autoApprove ? 'ON' : 'OFF'}`;
                    
                    await bot.editMessageText(statsText, {
                        chat_id: chatId,
                        message_id: messageId,
                        parse_mode: 'Markdown',
                        reply_markup: {
                            inline_keyboard: [
                                [
                                    { text: '🔙 Back', callback_data: 'super_panel' },
                                    { text: '🔄 Refresh', callback_data: 'super_stats' }
                                ]
                            ]
                        }
                    });
                    break;
                    
                case 'tools':
                    const toolsText = `🔧 *SUPER ADMIN TOOLS*\n\n` +
                                    `*Quick Actions:*\n` +
                                    `• /super backup - Create backup\n` +
                                    `• /super status [id] - Check group status\n` +
                                    `• /super fix [id] - Fix group issues\n` +
                                    `• /super delete [id] - Delete group\n\n` +
                                    `*Maintenance:*\n` +
                                    `• /super migrate [old] [new] - Migrate data\n` +
                                    `• /super broadcast [msg] - Broadcast message\n` +
                                    `• /super autoapprove on - Enable auto-approve`;
                    
                    await bot.editMessageText(toolsText, {
                        chat_id: chatId,
                        message_id: messageId,
                        parse_mode: 'Markdown',
                        reply_markup: {
                            inline_keyboard: [
                                [
                                    { text: '🔙 Back', callback_data: 'super_panel' },
                                    { text: '📋 Groups', callback_data: 'super_listgroups' }
                                ]
                            ]
                        }
                    });
                    break;
                    
                case 'refresh':
                    const currentAction = data.split('_')[1];
                    if (currentAction === 'panel') {
                        const refreshedPanel = await showSuperAdminPanel(chatId);
                        await bot.editMessageText(refreshedPanel.text, {
                            chat_id: chatId,
                            message_id: messageId,
                            parse_mode: 'Markdown',
                            reply_markup: refreshedPanel.keyboard.reply_markup
                        });
                    }
                    break;
                    
                case 'close':
                    await bot.deleteMessage(chatId, messageId);
                    break;
            }
        }
        
    } catch (error) {
        log('error', `Callback error: ${error.message}`);
    }
});

// ================= STARTUP =================
async function startBot() {
    try {
        console.log('\n' + '='.repeat(60));
        console.log('🚀 FINANCE BOT - MULTI GROUP VERSION');
        console.log('='.repeat(60));
        console.log(`⏰ Timezone: ${CONFIG.TIMEZONE}`);
        console.log(`👑 Super Admins: ${CONFIG.SUPER_ADMIN_IDS.length}`);
        console.log(`🔧 Debug Mode: ${process.env.DEBUG === 'true' ? 'ON' : 'OFF'}`);
        
        // Load data first
        const loaded = await loadAllData();
        if (!loaded) {
            console.log('❌ Failed to load data, starting fresh...');
        }
        
        // Get bot info
        const me = await bot.getMe();
        console.log(`🤖 Bot: @${me.username} (${me.id})`);
        console.log(`👥 Groups Loaded: ${Object.keys(groupsData).length}`);
        console.log(`✅ Auto Approve: ${globalConfig.autoApprove ? 'ON' : 'OFF'}`);
        console.log(`📋 Whitelist: ${globalConfig.whitelist.length} groups`);
        console.log(`🚫 Blacklist: ${globalConfig.blacklist.length} groups`);
        
        console.log('\n✅ BOT READY! 24/7 ONLINE');
        console.log('='.repeat(60) + '\n');
        
        // Auto-save interval
        const autoSaveInterval = setInterval(async () => {
            try {
                const saved = await saveAllData();
                if (saved) {
                    log('system', 'Auto-save completed');
                }
            } catch (error) {
                log('error', `Auto-save failed: ${error.message}`);
            }
        }, CONFIG.AUTO_SAVE_INTERVAL);
        
        // Daily reset check (every minute)
        const dailyResetInterval = setInterval(() => {
            try {
                const now = moment().tz(CONFIG.TIMEZONE);
                const today = now.format('YYYY-MM-DD');
                
                for (const [chatId, groupData] of Object.entries(groupsData)) {
                    if (groupData.config?.autoResetDaily && 
                        groupData.memory?.dailySpent?.lastReset !== today) {
                        
                        // Initialize if not exists
                        if (!groupData.memory.dailySpent) {
                            groupData.memory.dailySpent = {
                                USD: 0,
                                limit: groupData.config.dailyLimit || CONFIG.DEFAULT_DAILY_LIMIT,
                                lastReset: today,
                                resetTime: now.format('HH:mm:ss'),
                                warnings: []
                            };
                        } else {
                            groupData.memory.dailySpent.USD = 0;
                            groupData.memory.dailySpent.lastReset = today;
                            groupData.memory.dailySpent.resetTime = now.format('HH:mm:ss');
                            groupData.memory.dailySpent.warnings = [];
                        }
                        
                        log('info', `Daily reset for group ${chatId}`, { 
                            date: today,
                            name: groupData.name 
                        });
                        
                        // Notify group if enabled
                        if (groupData.config.notifyOnLimit && groupData.enabled) {
                            bot.sendMessage(chatId,
                                `🔄 *RESET HARIAN* (${now.format('HH:mm')})\n\n` +
                                `Limit harian udah direset ke $${groupData.config.dailyLimit}!\n` +
                                `Gas transaksi lagi bro! 💸`,
                                { 
                                    parse_mode: 'Markdown',
                                    reply_markup: getGroupKeyboard(parseInt(chatId), chatId).reply_markup
                                }
                            ).catch(error => {
                                log('error', `Failed to send reset notification to ${chatId}: ${error.message}`);
                            });
                        }
                    }
                }
                
                // Save after reset
                saveAllData().catch(() => {});
                
            } catch (error) {
                log('error', `Daily reset error: ${error.message}`);
            }
        }, 60000); // Check every minute
        
        // Monthly reset check (every hour)
        const monthlyResetInterval = setInterval(() => {
            try {
                const now = moment().tz(CONFIG.TIMEZONE);
                const currentMonth = now.format('YYYY-MM');
                
                for (const [chatId, groupData] of Object.entries(groupsData)) {
                    if (groupData.memory?.monthlySpent?.month !== currentMonth) {
                        
                        // Initialize if not exists
                        if (!groupData.memory.monthlySpent) {
                            groupData.memory.monthlySpent = {
                                USD: 0,
                                limit: groupData.config.monthlyLimit || CONFIG.DEFAULT_MONTHLY_LIMIT,
                                month: currentMonth,
                                categories: {}
                            };
                        } else {
                            groupData.memory.monthlySpent.USD = 0;
                            groupData.memory.monthlySpent.month = currentMonth;
                            groupData.memory.monthlySpent.categories = {};
                        }
                        
                        log('info', `Monthly reset for group ${chatId}`, { 
                            month: currentMonth,
                            name: groupData.name 
                        });
                        
                        // Notify group if enabled
                        if (groupData.config.notifyOnLimit && groupData.enabled) {
                            bot.sendMessage(chatId,
                                `🔄 *RESET BULANAN* (${now.format('MMMM YYYY')})\n\n` +
                                `Limit bulanan udah direset ke $${groupData.config.monthlyLimit}!\n` +
                                `Mulai bulan baru nih bro! 📅`,
                                { 
                                    parse_mode: 'Markdown',
                                    reply_markup: getGroupKeyboard(parseInt(chatId), chatId).reply_markup
                                }
                            ).catch(error => {
                                log('error', `Failed to send monthly reset notification to ${chatId}: ${error.message}`);
                            });
                        }
                    }
                }
                
                // Save after reset
                saveAllData().catch(() => {});
                
            } catch (error) {
                log('error', `Monthly reset error: ${error.message}`);
            }
        }, 3600000); // Check every hour
        
        // Clean up pending confirmations (every 5 minutes)
        const cleanupInterval = setInterval(() => {
            const now = Date.now();
            let cleaned = 0;
            
            for (const [id, pending] of Object.entries(pendingConfirmations)) {
                if (now - pending.timestamp > 60000) { // 1 minute timeout
                    delete pendingConfirmations[id];
                    cleaned++;
                }
            }
            
            if (cleaned > 0) {
                log('system', `Cleaned up ${cleaned} expired confirmations`);
            }
        }, 300000); // Every 5 minutes
        
        // Handle shutdown
        const cleanup = () => {
            clearInterval(autoSaveInterval);
            clearInterval(dailyResetInterval);
            clearInterval(monthlyResetInterval);
            clearInterval(cleanupInterval);
        };
        
        process.on('SIGINT', async () => {
            cleanup();
            console.log('\n🛑 SHUTDOWN SIGNAL RECEIVED');
            try {
                await saveAllData();
                console.log('💾 All data saved');
            } catch (error) {
                console.error('❌ Save failed:', error.message);
            }
            console.log('👋 GOODBYE');
            process.exit(0);
        });
        
        process.on('SIGTERM', async () => {
            cleanup();
            console.log('\n🛑 TERMINATION SIGNAL RECEIVED');
            try {
                await saveAllData();
                console.log('💾 All data saved');
            } catch (error) {
                console.error('❌ Save failed:', error.message);
            }
            process.exit(0);
        });
        
    } catch (error) {
        console.error('❌ STARTUP ERROR:', error);
        console.error('Stack:', error.stack);
        process.exit(1);
    }
}

// ================= ERROR HANDLERS =================
process.on('uncaughtException', async (error) => {
    log('error', `CRASH: ${error.message}`, error.stack);
    
    try {
        await saveAllData();
        console.log('💾 Emergency save successful');
    } catch (e) {
        console.error('❌ Emergency save failed:', e.message);
    }
    
    setTimeout(() => {
        console.log('💥 RESTARTING IN 5 SECONDS...');
        process.exit(1);
    }, 5000);
});

process.on('unhandledRejection', (reason, promise) => {
    log('error', `UNHANDLED REJECTION: ${reason}`);
    if (reason instanceof Error) {
        log('error', `Stack: ${reason.stack}`);
    }
});

// ================= START BOT =================
startBot();

