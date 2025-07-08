require('dotenv').config();
const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode');
const TelegramBot = require('node-telegram-bot-api');

const TELEGRAM_TOKEN = process.env.TELEGRAM_BOT_TOKEN;
const TELEGRAM_CHAT_ID = process.env.TELEGRAM_CHAT_ID;

console.log('Enviando QR code para o chat ID:', TELEGRAM_CHAT_ID);

const bot = new TelegramBot(TELEGRAM_TOKEN);

const client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: { headless: true, args: ['--no-sandbox', '--disable-setuid-sandbox'] }
});

let lastTelegramQrMsgId = null;

client.on('qr', async (qrCode) => {
    try {
        console.log('Gerando buffer do QR code...');
        const qrImageBuffer = await qrcode.toBuffer(qrCode);
        if (lastTelegramQrMsgId) {
            // Tenta apagar o QR anterior para não confundir
            await bot.deleteMessage(TELEGRAM_CHAT_ID, lastTelegramQrMsgId).catch(() => {});
            lastTelegramQrMsgId = null;
        }
        console.log('Enviando QR code para o Telegram...');
        const sentMsg = await bot.sendPhoto(TELEGRAM_CHAT_ID, qrImageBuffer, { caption: 'Escaneie este QR code para autenticar o WhatsApp.' });
        lastTelegramQrMsgId = sentMsg.message_id;
        console.log('QR code enviado com sucesso para o Telegram!');
    } catch (err) {
        console.error('Erro ao enviar QR code para o Telegram:', err);
    }
});

client.on('ready', async () => {
    console.log('Cliente está pronto!');
    if (lastTelegramQrMsgId) {
        await bot.deleteMessage(TELEGRAM_CHAT_ID, lastTelegramQrMsgId).catch(() => {});
        lastTelegramQrMsgId = null;
    }
    await bot.sendMessage(TELEGRAM_CHAT_ID, '✅ WhatsApp autenticado com sucesso!');
    // Não encerra o processo, mantém o cliente ativo
});

client.on('auth_failure', () => {
    console.error('Falha na autenticação. Será necessário escanear o QR novamente.');
    bot.sendMessage(TELEGRAM_CHAT_ID, '❌ Falha na autenticação do WhatsApp. Escaneie o QR code novamente.');
});

client.on('disconnected', (reason) => {
    console.log('Cliente desconectado:', reason);
    bot.sendMessage(TELEGRAM_CHAT_ID, `⚠️ WhatsApp desconectado: ${reason}`);
});

client.initialize(); 