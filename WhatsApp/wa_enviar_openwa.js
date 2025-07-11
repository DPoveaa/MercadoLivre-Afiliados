const { create, Whatsapp } = require('@open-wa/wa-automate');
const fs = require('fs');
const path = require('path');
const fetch = require('node-fetch');
require('dotenv').config();

let client = null;
let isConnected = false;

function log(message) {
    const timestamp = new Date().toISOString().replace('T', ' ').substr(0, 19);
    console.log(`[${timestamp}] ${message}`);
}

async function initializeOpenWA() {
    if (client && isConnected) {
        return client;
    }

    try {
        log("Iniciando Open-WA...");
        
        client = await create({
            sessionId: "default",
            multiDevice: true,
            headless: true,
            qrTimeout: 0,
            authTimeout: 0,
            autoRefresh: true,
            cacheEnabled: true,
            useChrome: true,
            chromiumVersion: '818858',
            chromiumArgs: [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--no-first-run',
                '--no-zygote',
                '--disable-gpu'
            ]
        });

        isConnected = true;
        log("✅ Open-WA conectado com sucesso!");
        return client;
    } catch (error) {
        log(`❌ Erro ao inicializar Open-WA: ${error.message}`);
        throw error;
    }
}

async function sendTextMessage(chatId, message) {
    try {
        const wa = await initializeOpenWA();
        
        log(`Enviando texto para ${chatId}`);
        const result = await wa.sendText(chatId, message);
        
        if (result) {
            log(`✅ Mensagem enviada para ${chatId}`);
            return true;
        } else {
            log(`❌ Falha ao enviar mensagem para ${chatId}`);
            return false;
        }
    } catch (error) {
        log(`❌ Erro ao enviar texto: ${error.message}`);
        return false;
    }
}

async function sendImageMessage(chatId, message, imageUrl) {
    try {
        const wa = await initializeOpenWA();
        
        log(`Enviando imagem para ${chatId}`);
        log(`URL da imagem: ${imageUrl}`);
        
        // Download da imagem
        const response = await fetch(imageUrl);
        if (!response.ok) {
            throw new Error(`Falha ao baixar imagem: ${response.status}`);
        }
        
        const imageBuffer = await response.arrayBuffer();
        const tempPath = path.join(__dirname, 'temp_image.jpg');
        
        // Salva temporariamente
        fs.writeFileSync(tempPath, Buffer.from(imageBuffer));
        
        // Envia imagem com legenda
        const result = await wa.sendImage(chatId, tempPath, 'image.jpg', message);
        
        // Remove arquivo temporário
        fs.unlinkSync(tempPath);
        
        if (result) {
            log(`✅ Imagem enviada para ${chatId}`);
            return true;
        } else {
            log(`❌ Falha ao enviar imagem para ${chatId}`);
            return false;
        }
    } catch (error) {
        log(`❌ Erro ao enviar imagem: ${error.message}`);
        // Fallback para texto
        log("Tentando fallback: enviando só o texto");
        return await sendTextMessage(chatId, message);
    }
}

async function sendWhatsAppToMultipleTargets(message, imageUrl = null) {
    const TEST_MODE = process.env.TEST_MODE === 'true';
    const results = {};
    
    try {
        if (TEST_MODE) {
            const groupId = process.env.WHATSAPP_GROUP_ID_TESTE || "120363399821087134@g.us";
            
            if (imageUrl) {
                results['grupo_teste'] = await sendImageMessage(groupId, message, imageUrl);
            } else {
                results['grupo_teste'] = await sendTextMessage(groupId, message);
            }
        } else {
            const groupId = process.env.WHATSAPP_GROUP_ID || "120363400146352860@g.us";
            const channelId = process.env.WHATSAPP_CHANNEL_ID || "120363401669269114@newsletter";
            
            if (imageUrl) {
                results['grupo'] = await sendImageMessage(groupId, message, imageUrl);
                results['canal'] = await sendImageMessage(channelId, message, imageUrl);
            } else {
                results['grupo'] = await sendTextMessage(groupId, message);
                results['canal'] = await sendTextMessage(channelId, message);
            }
        }
        
        log(`Resultado envio WhatsApp: ${JSON.stringify(results)}`);
        return results;
    } catch (error) {
        log(`❌ Erro geral no envio WhatsApp: ${error.message}`);
        return { error: error.message };
    }
}

async function healthcheck() {
    try {
        const wa = await initializeOpenWA();
        return wa && isConnected;
    } catch (error) {
        log(`❌ Healthcheck falhou: ${error.message}`);
        return false;
    }
}

async function notifyTelegramConnectionIssue() {
    const { sendTelegramMessage } = require('../Telegram/tl_enviar.js');
    
    const TELEGRAM_BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN;
    const TELEGRAM_CHAT_ID1 = process.env.TELEGRAM_CHAT_ID;
    const TELEGRAM_CHAT_ID2 = process.env.TELEGRAM_CHAT_ID2;
    
    if (!TELEGRAM_BOT_TOKEN || !TELEGRAM_CHAT_ID1) {
        log("Erro: TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID não configurados");
        return false;
    }
    
    const message = (
        "⚠️ *ALERTA: Problema de Conexão WhatsApp*\n\n" +
        "O WhatsApp desconectou ou precisa de reautenticação.\n" +
        "Verifique a conexão do Open-WA.\n\n" +
        "*Status:* Aguardando reconexão automática"
    );
    
    const results = {};
    
    // Envia para o primeiro chat
    results['chat1'] = await sendTelegramMessage(
        message,
        null,
        TELEGRAM_BOT_TOKEN,
        TELEGRAM_CHAT_ID1
    );
    
    // Envia para o segundo chat, se existir
    if (TELEGRAM_CHAT_ID2) {
        results['chat2'] = await sendTelegramMessage(
            message,
            null,
            TELEGRAM_BOT_TOKEN,
            TELEGRAM_CHAT_ID2
        );
    }
    
    return results;
}

// Função para aguardar autenticação
async function waitForWhatsAppAuth(checkInterval = 10) {
    log("🔍 Verificando autenticação do WhatsApp...");
    
    while (true) {
        if (await healthcheck()) {
            log("✅ WhatsApp autenticado e pronto!");
            return true;
        } else {
            log("❌ WhatsApp não autenticado! Aguardando QR code...");
            await notifyTelegramConnectionIssue();
            log(`⏳ Aguardando autenticação... (verificando novamente em ${checkInterval} segundos)`);
            await new Promise(resolve => setTimeout(resolve, checkInterval * 1000));
        }
    }
}

module.exports = {
    sendWhatsAppToMultipleTargets,
    healthcheck,
    notifyTelegramConnectionIssue,
    waitForWhatsAppAuth,
    initializeOpenWA
}; 