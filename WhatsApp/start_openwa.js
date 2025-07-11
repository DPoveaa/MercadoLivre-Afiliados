const { create } = require('@open-wa/wa-automate');
const fs = require('fs');
const path = require('path');

async function startOpenWA() {
    try {
        console.log("🚀 Iniciando Open-WA...");
        
        const client = await create({
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

        console.log("✅ Open-WA iniciado com sucesso!");
        console.log("📱 Aguardando QR Code para autenticação...");
        
        // Mantém o processo rodando
        process.on('SIGINT', async () => {
            console.log("🛑 Encerrando Open-WA...");
            await client.kill();
            process.exit(0);
        });
        
    } catch (error) {
        console.error("❌ Erro ao iniciar Open-WA:", error.message);
        process.exit(1);
    }
}

startOpenWA(); 