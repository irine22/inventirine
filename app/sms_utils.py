import logging

def _send_sms_simulated(phone_number, message):
    """
    Simulates sending an SMS message. In production, this would integrate 
    with Twilio, AWS SNS, or Vonage.
    """
    try:
        # Print clearly to console for simulation/testing
        print(f"\n{'='*50}")
        print(f"📱 SIMULATED SMS TO: {phone_number}")
        print(f"✉️ MESSAGE: {message}")
        print(f"{'='*50}\n")
        
        logging.info(f"Simulated SMS sent to {phone_number}: {message}")
        return True
    except Exception as e:
        logging.error(f"Failed to simulate SMS: {e}")
        return False
