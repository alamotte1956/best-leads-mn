const { defineConfig, devices } = require('@playwright/test');
module.exports=defineConfig({
  testDir: './browser-tests', outputDir:'./test-results', timeout:90000,
  fullyParallel:true,workers:2,retries:0,reporter:'list',
  use:{baseURL:'http://127.0.0.1:5055',screenshot:'only-on-failure',trace:'retain-on-failure'},
  webServer:{command:'python ci/browser_fixture.py',cwd:require('path').resolve(__dirname,'..'),
    url:'http://127.0.0.1:5055/health',reuseExistingServer:false,timeout:30000},
  projects:[
    {name:'Chromium',use:{...devices['Desktop Chrome']}},
    {name:'Google Chrome',use:{...devices['Desktop Chrome'],channel:'chrome'}},
    {name:'Microsoft Edge',use:{...devices['Desktop Edge'],channel:'msedge'}},
    {name:'Firefox',use:{...devices['Desktop Firefox']}},
    {name:'WebKit',use:{...devices['Desktop Safari']}},
    {name:'Android Chrome emulation',use:{...devices['Pixel 7']}},
    {name:'iPhone Safari emulation',use:{...devices['iPhone 13']}},
  ],
});
