const puppeteer = require('puppeteer');

function delay(time) {
   return new Promise(function(resolve) { 
       setTimeout(resolve, time)
   });
};

(async () => {
    // Launch a new browser instance
    const browser = await puppeteer.launch({headless: "new"});
    // Create a new page
    const page = await browser.newPage();
    // Navigate to the specified URL
    await page.goto('SCRAPE_URL', { waitUntil: 'networkidle2' });
    
    // Get the page's source code
    const sourceCode = await page.content();

    // Print the source code to standard output
    console.log(sourceCode);

    // Close the browser
    await browser.close();
})();
