/*const now = new Date();
const hour = now.getHours();
if (hour >= 6 && hour < 10) {
    setTimeout(() => location.reload(), 300000); // 5 minutes
}
*/

function scheduleRefresh() {
    const now = new Date();
    const hour = now.getHours();

    if (hour >= 6 && hour < 10) {
        setTimeout(() => {
            location.reload();
        }, 300000); // 5 minutes
    } else {
        // Check again in 5 minutes to see if we're in the window
        setTimeout(scheduleRefresh, 300000);
    }
}

// Start the loop
scheduleRefresh();

