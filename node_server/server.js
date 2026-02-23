const express = require('express');
const bodyParser = require('body-parser');
const puppeteer = require('puppeteer');
const cors = require('cors');
const crypto = require('crypto');

const app = express();

// Lock CORS to Flask origin only
const FLASK_ORIGIN = process.env.FLASK_ORIGIN || 'http://localhost:5000';
app.use(cors({ origin: FLASK_ORIGIN }));
app.use(bodyParser.json());

// PDF token secret — must match Flask's PDF_TOKEN_SECRET
const PDF_TOKEN_SECRET = process.env.PDF_TOKEN_SECRET || '';

/**
 * Verify signed PDF token from Flask.
 * Token format: { token, student_id, expiry, signature }
 * Signature = HMAC-SHA256(token:student_id:expiry, PDF_TOKEN_SECRET)
 */
function verifyPdfToken(token, studentId, expiry, signature) {
    // Check expiry
    if (Math.floor(Date.now() / 1000) > parseInt(expiry, 10)) {
        return false;
    }

    // Recompute signature
    const payload = `${token}:${studentId}:${expiry}`;
    const expectedSignature = crypto
        .createHmac('sha256', PDF_TOKEN_SECRET)
        .update(payload)
        .digest('hex');

    // Constant-time comparison
    try {
        return crypto.timingSafeEqual(
            Buffer.from(signature, 'hex'),
            Buffer.from(expectedSignature, 'hex')
        );
    } catch {
        return false;
    }
}

app.post('/generate-pdf', async (req, res) => {
    const { url, token, student_id, expiry, signature } = req.body;

    if (!url) {
        return res.status(400).json({ error: 'Missing URL' });
    }

    // Validate PDF token if PDF_TOKEN_SECRET is configured
    if (PDF_TOKEN_SECRET) {
        if (!token || !student_id || !expiry || !signature) {
            return res.status(401).json({ error: 'Missing authentication token' });
        }

        if (!verifyPdfToken(token, student_id, expiry, signature)) {
            return res.status(403).json({ error: 'Invalid or expired token' });
        }
    }

    try {
        const browser = await puppeteer.launch({
            headless: 'new',
            args: ['--no-sandbox', '--disable-setuid-sandbox'],
        });

        const page = await browser.newPage();
        await page.goto(url, { waitUntil: 'networkidle0' });

        // Activate print styles
        await page.emulateMediaType('print');

        // Remove the download button container before PDF generation
        await page.evaluate(() => {
            const btn = document.querySelector('.button-container');
            if (btn) btn.remove();
        });

        const pdfBuffer = await page.pdf({
            format: 'A4',
            printBackground: true,
            margin: {
                top: '0cm',
                bottom: '0cm',
                left: '0cm',
                right: '0cm'
            },
            preferCSSPageSize: false,
        });

        await browser.close();

        res.set({
            'Content-Type': 'application/pdf',
            'Content-Disposition': 'attachment; filename="MYCAREERCHOICES.pdf"',
        });

        res.send(pdfBuffer);
    } catch (err) {
        console.error('Puppeteer error:', err);
        res.status(500).send('Failed to generate PDF');
    }
});

// Token verification endpoint for Flask to check token validity
app.post('/verify-token', (req, res) => {
    const { token, student_id, expiry, signature } = req.body;

    if (!PDF_TOKEN_SECRET) {
        return res.json({ valid: true });
    }

    if (!token || !student_id || !expiry || !signature) {
        return res.status(400).json({ valid: false, error: 'Missing fields' });
    }

    const valid = verifyPdfToken(token, student_id, expiry, signature);
    return res.json({ valid });
});

app.listen(3000, () => {
    console.log('Puppeteer PDF server running at http://localhost:3000');
});
