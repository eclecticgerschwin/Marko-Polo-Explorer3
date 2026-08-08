// ── Marko Polo Explorer Website Interactivity ─────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // OS Selector Tab Switcher
  window.switchOsTab = function(osName) {
    const macTab = document.getElementById('tabMacBtn');
    const winTab = document.getElementById('tabWinBtn');
    const macContent = document.getElementById('osContentMac');
    const winContent = document.getElementById('osContentWin');

    if (!macTab || !winTab || !macContent || !winContent) return;

    if (osName === 'mac') {
      macTab.classList.add('active');
      winTab.classList.remove('active');
      macContent.style.display = 'block';
      winContent.style.display = 'none';
    } else {
      winTab.classList.add('active');
      macTab.classList.remove('active');
      winContent.style.display = 'block';
      macContent.style.display = 'none';
    }
  };

  // Copy Code Snippet Helper
  window.copyCode = function(button, elementId) {
    const codeElem = document.getElementById(elementId);
    if (!codeElem) return;

    const textToCopy = codeElem.textContent.trim();
    navigator.clipboard.writeText(textToCopy).then(() => {
      const originalText = button.textContent;
      button.textContent = '✓ Copied!';
      button.style.background = '#30d158';
      button.style.color = '#fff';
      setTimeout(() => {
        button.textContent = originalText;
        button.style.background = '';
        button.style.color = '';
      }, 2000);
    }).catch(err => {
      console.error('Failed to copy text: ', err);
    });
  };

  // Mobile Navigation Hamburger Toggle
  const navToggle = document.getElementById('mobileNavToggle');
  const navLinks = document.getElementById('navLinks');

  if (navToggle && navLinks) {
    navToggle.addEventListener('click', (e) => {
      e.stopPropagation();
      navToggle.classList.toggle('active');
      navLinks.classList.toggle('active');
    });

    // Close mobile nav when clicking any link inside
    navLinks.querySelectorAll('a').forEach(link => {
      link.addEventListener('click', () => {
        navToggle.classList.remove('active');
        navLinks.classList.remove('active');
      });
    });

    // Close when clicking outside
    document.addEventListener('click', (e) => {
      if (!navToggle.contains(e.target) && !navLinks.contains(e.target)) {
        navToggle.classList.remove('active');
        navLinks.classList.remove('active');
      }
    });
  }

  // Handle Contact Form Status Banner from URL
  const urlParams = new URLSearchParams(window.location.search);
  const status = urlParams.get('status');
  if (status === 'success') {
    const banner = document.getElementById('formStatusSuccess');
    if (banner) banner.style.display = 'block';
  } else if (status === 'error') {
    const banner = document.getElementById('formStatusError');
    if (banner) banner.style.display = 'block';
  }

  // Handle Bug & Contact Form Submission (Multi-layer Fallback)
  const contactForm = document.getElementById('bugContactForm');
  const successBanner = document.getElementById('formStatusSuccess');
  const errorBanner = document.getElementById('formStatusError');

  if (contactForm) {
    contactForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      
      const submitBtn = contactForm.querySelector('button[type="submit"]');
      const origBtnText = submitBtn ? submitBtn.innerHTML : '';
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '⏳ Sending Message...';
      }

      if (successBanner) successBanner.style.display = 'none';
      if (errorBanner) errorBanner.style.display = 'none';

      const formData = new FormData(contactForm);
      const name = formData.get('name') || '';
      const email = formData.get('email') || '';
      const category = formData.get('category') || '';
      const os = formData.get('os') || '';
      const message = formData.get('message') || '';

      let sentSuccessfully = false;

      // Attempt 1: Direct HTTPS API Delivery (Does not require PHP mail() or sendmail)
      try {
        const fsData = new FormData();
        fsData.append('name', name);
        fsData.append('email', email);
        fsData.append('category', category);
        fsData.append('os', os);
        fsData.append('message', message);
        fsData.append('_subject', 'Marko Polo contact form');
        fsData.append('_captcha', 'false');

        const fsResp = await fetch('https://formsubmit.co/ajax/mcpseidon@gmail.com', {
          method: 'POST',
          body: fsData,
          headers: { 'Accept': 'application/json' }
        });
        if (fsResp.ok) {
          sentSuccessfully = true;
        }
      } catch (err) {
        console.warn('Direct HTTPS API failed, trying send_mail.php...', err);
      }

      // Attempt 2: send_mail.php cURL Proxy
      if (!sentSuccessfully) {
        try {
          const phpResp = await fetch('send_mail.php', {
            method: 'POST',
            body: formData
          });
          if (phpResp.ok) {
            sentSuccessfully = true;
          }
        } catch (err) {
          console.warn('send_mail.php failed, falling back to mailto...', err);
        }
      }

      // Attempt 3: Native Mailto Link Fallback
      if (!sentSuccessfully) {
        const subject = encodeURIComponent('Marko Polo contact form');
        const bodyText = encodeURIComponent(
          `Name: ${name}\nEmail: ${email}\nCategory: ${category}\nOS: ${os}\n\nMessage:\n${message}`
        );
        window.location.href = `mailto:mcpseidon@gmail.com?subject=${subject}&body=${bodyText}`;
        sentSuccessfully = true;
      }

      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = origBtnText;
      }

      if (sentSuccessfully && successBanner) {
        successBanner.style.display = 'block';
        contactForm.reset();
        successBanner.scrollIntoView({ behavior: 'smooth', block: 'center' });
      } else if (!sentSuccessfully && errorBanner) {
        errorBanner.style.display = 'block';
      }
    });
  }
});
