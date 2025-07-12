import io
import os
from fontTools.ttLib import ttFont
from PIL import Image, ImageDraw, ImageFont
from paddlex import create_pipeline
from lib import woff2_to_ttf, get_charater_hex
from slow import draw, IMAGE_SIZE, FONT_SIZE, match_test_im_with_cache, init_true_font, load_std_guest_range

# Initialize PaddleX OCR pipeline
ocr = create_pipeline(pipeline="OCR")

def extract_characters_with_paddleocr(font_path: str, std_font_dict=None, guest_range=None, TRUE_FONT_PATH=None, limit_chars: int | None = None) -> dict[str, str]:
    """
    Extracts characters from a font file and maps them to recognized characters using OCR with fallback to image similarity.

    Args:
        font_path: Path to the font file (WOFF2, TTF, or OTF).
        std_font_dict: Dictionary of standard fonts for fallback (optional).
        guest_range: List of characters to match against for fallback (optional).
        TRUE_FONT_PATH: Path to true font files for fallback (optional).
        limit_chars: Limit processing to first N characters (for testing purposes).

    Returns:
        A dictionary mapping font characters to their recognized characters:
        {
            font_char: 'recognized_char'
        }
    """
    if font_path.lower().endswith('.woff2'):
        with open(font_path, 'rb') as f:
            font_bytes = f.read()
        ttf_font = woff2_to_ttf(font_bytes)
        # Save TTF to a temporary file as Pillow needs a file path or a file-like object
        # that supports seek, which BytesIO from woff2_to_ttf doesn't fully provide for ImageFont
        temp_ttf_file = io.BytesIO()
        ttf_font.save(temp_ttf_file)
        temp_ttf_file.seek(0)
        pil_font = ImageFont.truetype(temp_ttf_file, FONT_SIZE)
        # Get characters from the TTFont object
        characters = set()
        for table in ttf_font['cmap'].tables:
            for char_code in table.cmap:
                character = chr(char_code)
                characters.add(character)
        # Convert set to list to maintain an order, though order isn't strictly necessary here
        characters = list(characters)
        print(f"First 10 characters from font (WOFF2): {characters[:10]}")


    elif font_path.lower().endswith('.ttf') or font_path.lower().endswith('.otf'):
        pil_font = ImageFont.truetype(font_path, FONT_SIZE)
        # For TTF/OTF, we can also use fontTools to list characters to be consistent
        ft_font = ttFont.TTFont(font_path)
        characters = set()
        for table in ft_font['cmap'].tables:
            for char_code in table.cmap:
                character = chr(char_code)
                characters.add(character)
        characters = list(characters)
    else:
        raise ValueError("Unsupported font format. Please provide a WOFF2, TTF, or OTF file.")

    # Process ALL characters from the font (not just PUA characters)
    characters_to_process = characters
    
    # Apply character limit if specified (for testing)
    if limit_chars is not None and limit_chars > 0:
        characters_to_process = characters_to_process[:limit_chars]
        print(f"Limited processing to first {limit_chars} characters")
    
    print(f"Found {len(characters_to_process)} characters to process (processing all font characters)")
    
    char_to_char_map = {}
    # Create debug_images directory if it doesn't exist (relative to CWD)
    debug_image_dir = 'debug_ocr_images'
    if not os.path.exists(debug_image_dir):
        os.makedirs(debug_image_dir)

    saved_image_count = 0
    max_debug_images = 0 # save images for inspection, set to 0 to disable saving

    for char_to_render in characters_to_process:
        if not char_to_render.strip():  # Skip whitespace or control characters
            continue

        try:
            # Render character to image with OCR-optimized settings
            char_image_original = draw(char_to_render, pil_font, IMAGE_SIZE)

            # Convert 1-bit image to RGB for better OCR compatibility
            if char_image_original.mode == '1':
                # Convert 1-bit to RGB with proper scaling
                char_image_rgb = Image.new('RGB', char_image_original.size, 'white')
                # Create a high-contrast RGB version
                pixels = char_image_original.load()
                rgb_pixels = char_image_rgb.load()
                for y in range(char_image_original.height):
                    for x in range(char_image_original.width):
                        if pixels[x, y] == 0:  # Black pixel in 1-bit mode
                            rgb_pixels[x, y] = (0, 0, 0)  # Black
                        else:
                            rgb_pixels[x, y] = (255, 255, 255)  # White
                char_image_original = char_image_rgb

            # Check if the image is mostly white (blank glyph detection)
            test_image_l = char_image_original.convert('L')
            extrema = test_image_l.getextrema()
            
            # More robust blank detection for RGB images
            if extrema[0] == extrema[1] and extrema[0] >= 250:
                print(f"Skipping OCR for char '{char_to_render}' (ord: {ord(char_to_render)}) as rendered image appears blank/mostly white.")
                continue

            # Enhanced padding for OCR - larger padding for better recognition
            padding = 20  # Increased padding for better OCR context
            new_size = (char_image_original.width + 2 * padding, char_image_original.height + 2 * padding)
            char_image_padded = Image.new('RGB', new_size, (255, 255, 255))  # White background
            
            # Center the character in the padded area
            paste_x = (new_size[0] - char_image_original.width) // 2
            paste_y = (new_size[1] - char_image_original.height) // 2
            char_image_padded.paste(char_image_original, (paste_x, paste_y))
            
            # Use RGB image directly (no BGR conversion needed for PaddleX)
            char_image_rgb = char_image_padded

            # Convert PIL image to numpy array
            import numpy as np

            # Save image for debugging if count is less than max
            if saved_image_count < max_debug_images:
                try:
                    # Sanitize filename
                    safe_char_name = "".join(c if c.isalnum() else "_" for c in char_to_render)
                    if not safe_char_name: # handle cases where char might be purely symbolic
                        safe_char_name = f"char_ord_{ord(char_to_render)}"

                    print(f"Attempting to save debug image for char: '{char_to_render}' (ord: {ord(char_to_render)}) as ocr_input_{saved_image_count}_{safe_char_name}.png")
                    debug_image_path = os.path.join(debug_image_dir, f"ocr_input_{saved_image_count}_{safe_char_name}.png")
                    char_image_rgb.save(debug_image_path) # Save the RGB PIL image
                    # print(f"Saved debug image to {debug_image_path}") # Optional: print path
                    saved_image_count += 1
                except Exception as img_save_e:
                    print(f"Could not save debug image for char '{char_to_render}': {img_save_e}")

            img_np = np.array(char_image_rgb)

            # Perform OCR using PaddleX with optimized parameters for single character recognition
            ocr_results = ocr.predict(
                input=img_np,
                use_doc_orientation_classify=False,  # Disable document orientation for single chars
                use_doc_unwarping=False,            # Disable document unwarping for single chars
                use_textline_orientation=False,     # Keep textline orientation disabled
            )
            
            # Convert generator to list
            ocr_results_list = list(ocr_results)
            
            # Debug: print actual result structure to understand the API response
            print(f"DEBUG: OCR results list length: {len(ocr_results_list)}")
            
            if ocr_results_list:
                ocr_result = ocr_results_list[0]  # Get the first (and likely only) result
                print(f"DEBUG: OCR result type: {type(ocr_result)}")
                
                # Access recognized texts from PaddleX OCRResult (dict-style access)
                if 'rec_texts' in ocr_result and ocr_result['rec_texts']:
                    recognized_texts = ocr_result['rec_texts']
                    confidence_scores = ocr_result.get('rec_scores', [])
                    print(f"DEBUG: Found {len(recognized_texts)} recognized texts: {recognized_texts}")
                    if confidence_scores:
                        print(f"DEBUG: Confidence scores: {confidence_scores}")
                    
                    # If we have recognized text
                    if recognized_texts and len(recognized_texts) > 0:
                        recognized_text = recognized_texts[0]  # Take the first recognized text
                        confidence = confidence_scores[0] if confidence_scores else 0.0
                        
                        # Map if a single character is recognized 
                        if recognized_text and len(recognized_text.strip()) == 1:
                            recognized_char = recognized_text.strip()
                            
                            # Check confidence threshold (only accept very high confidence results)
                            if confidence >= 0.95:
                                # Accept any recognized character (no restriction to Chinese characters)
                                char_to_char_map[char_to_render] = recognized_char
                                print(f"Successfully mapped '{char_to_render}' (U+{ord(char_to_render):04X}) -> '{recognized_char}' [confidence: {confidence:.3f}]")
                            else:
                                print(f"Low confidence recognition for '{char_to_render}': '{recognized_char}' [confidence: {confidence:.3f}] - using fallback")
                                # Use fallback for low confidence results
                                if std_font_dict and guest_range and TRUE_FONT_PATH:
                                    fallback_result = match_test_im_with_cache(char_image_rgb, std_font_dict, guest_range, TRUE_FONT_PATH)
                                    if fallback_result:
                                        char_to_char_map[char_to_render] = fallback_result
                                        print(f"Fallback matched '{char_to_render}' -> '{fallback_result}'")
                        else:
                            print(f"DEBUG: Unhandled recognized text: '{recognized_text}' (length: {len(recognized_text) if recognized_text else 0}) [confidence: {confidence:.3f}]")
                            # Try fallback for unhandled text
                            if std_font_dict and guest_range and TRUE_FONT_PATH:
                                fallback_result = match_test_im_with_cache(char_image_rgb, std_font_dict, guest_range, TRUE_FONT_PATH)
                                if fallback_result:
                                    char_to_char_map[char_to_render] = fallback_result
                                    print(f"Fallback matched '{char_to_render}' -> '{fallback_result}'")
                else:
                    print(f"DEBUG: No rec_texts found in result or rec_texts is empty")
                    # Try fallback when no OCR results
                    if std_font_dict and guest_range and TRUE_FONT_PATH:
                        fallback_result = match_test_im_with_cache(char_image_rgb, std_font_dict, guest_range, TRUE_FONT_PATH)
                        if fallback_result:
                            char_to_char_map[char_to_render] = fallback_result
                            print(f"Fallback matched '{char_to_render}' -> '{fallback_result}'")
            else:
                print(f"DEBUG: No OCR results returned")
                # Try fallback when no OCR results at all
                if std_font_dict and guest_range and TRUE_FONT_PATH:
                    fallback_result = match_test_im_with_cache(char_image_rgb, std_font_dict, guest_range, TRUE_FONT_PATH)
                    if fallback_result:
                        char_to_char_map[char_to_render] = fallback_result
                        print(f"Fallback matched '{char_to_render}' -> '{fallback_result}'")

        except Exception as e:
            # Try fallback when OCR fails completely
            if std_font_dict and guest_range and TRUE_FONT_PATH:
                try:
                    fallback_result = match_test_im_with_cache(char_image_rgb, std_font_dict, guest_range, TRUE_FONT_PATH)
                    if fallback_result:
                        char_to_char_map[char_to_render] = fallback_result
                        print(f"Fallback matched '{char_to_render}' -> '{fallback_result}' (OCR failed)")
                except Exception:
                    pass # Continue with other characters

    return char_to_char_map

def extract_single_character_ocr(char_to_render: str, pil_font, confidence_threshold: float = 0.95) -> tuple[str | None, float]:
    """
    Process a single character with OCR and return result with confidence.
    
    Args:
        char_to_render: Character to process
        pil_font: PIL font object for rendering
        confidence_threshold: Minimum confidence required for acceptance
        
    Returns:
        Tuple of (recognized_character, confidence) or (None, 0.0) for failures
    """
    if not char_to_render.strip():  # Skip whitespace or control characters
        return None, 0.0

    try:
        # Render character to image with OCR-optimized settings
        char_image_original = draw(char_to_render, pil_font, IMAGE_SIZE)

        # Convert 1-bit image to RGB for better OCR compatibility
        if char_image_original.mode == '1':
            char_image_rgb = Image.new('RGB', char_image_original.size, 'white')
            pixels = char_image_original.load()
            rgb_pixels = char_image_rgb.load()
            for y in range(char_image_original.height):
                for x in range(char_image_original.width):
                    if pixels[x, y] == 0:  # Black pixel in 1-bit mode
                        rgb_pixels[x, y] = (0, 0, 0)  # Black
                    else:
                        rgb_pixels[x, y] = (255, 255, 255)  # White
            char_image_original = char_image_rgb

        # Check if the image is mostly white (blank glyph detection)
        test_image_l = char_image_original.convert('L')
        extrema = test_image_l.getextrema()
        
        if extrema[0] == extrema[1] and extrema[0] >= 250:
            print(f"Skipping OCR for char '{char_to_render}' (ord: {ord(char_to_render)}) as rendered image appears blank/mostly white.")
            return None, 0.0

        # Enhanced padding for OCR
        padding = 20
        new_size = (char_image_original.width + 2 * padding, char_image_original.height + 2 * padding)
        char_image_padded = Image.new('RGB', new_size, (255, 255, 255))
        
        paste_x = (new_size[0] - char_image_original.width) // 2
        paste_y = (new_size[1] - char_image_original.height) // 2
        char_image_padded.paste(char_image_original, (paste_x, paste_y))
        
        char_image_rgb = char_image_padded

        # Convert PIL image to numpy array
        import numpy as np
        img_np = np.array(char_image_rgb)

        # Perform OCR using PaddleX
        ocr_results = ocr.predict(
            input=img_np,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
        
        ocr_results_list = list(ocr_results)
        
        if ocr_results_list:
            ocr_result = ocr_results_list[0]
            
            if 'rec_texts' in ocr_result and ocr_result['rec_texts']:
                recognized_texts = ocr_result['rec_texts']
                confidence_scores = ocr_result.get('rec_scores', [])
                
                if recognized_texts and len(recognized_texts) > 0:
                    recognized_text = recognized_texts[0]
                    confidence = confidence_scores[0] if confidence_scores else 0.0
                    
                    # Check if single character recognized and meets confidence threshold
                    if recognized_text and len(recognized_text.strip()) == 1:
                        recognized_char = recognized_text.strip()
                        
                        if confidence >= confidence_threshold:
                            print(f"OCR SUCCESS: '{char_to_render}' (U+{ord(char_to_render):04X}) -> '{recognized_char}' [confidence: {confidence:.3f}]")
                            return recognized_char, confidence
                        else:
                            print(f"OCR LOW CONFIDENCE: '{char_to_render}': '{recognized_char}' [confidence: {confidence:.3f}]")
                            return None, confidence
                    else:
                        print(f"OCR INVALID: '{char_to_render}' got '{recognized_text}' (length: {len(recognized_text) if recognized_text else 0})")
                        return None, confidence if 'confidence' in locals() else 0.0

        print(f"OCR FAILED: '{char_to_render}' - no valid recognition")
        return None, 0.0

    except Exception as e:
        print(f"OCR EXCEPTION: '{char_to_render}' - {str(e)}")
        return None, 0.0

def extract_characters_unified_workflow(font_path: str, std_font_dict=None, guest_range=None, TRUE_FONT_PATH=None, limit_chars: int | None = None) -> dict[str, str]:
    """
    Unified workflow: Use PaddleOCR first, then fallback to image similarity for failed characters only.
    
    Args:
        font_path: Path to the font file (WOFF2, TTF, or OTF).
        std_font_dict: Dictionary of standard fonts for fallback (optional).
        guest_range: List of characters to match against for fallback (optional).
        TRUE_FONT_PATH: Path to true font files for fallback (optional).
        limit_chars: Limit processing to first N characters (for testing purposes).

    Returns:
        A dictionary mapping font characters to their recognized characters:
        {
            font_char: 'recognized_char'
        }
    """
    print("=== UNIFIED WORKFLOW: PaddleOCR + Fallback ===")
    
    # Extract characters from font file (reuse existing logic)
    if font_path.lower().endswith('.woff2'):
        with open(font_path, 'rb') as f:
            font_bytes = f.read()
        ttf_font = woff2_to_ttf(font_bytes)
        temp_ttf_file = io.BytesIO()
        ttf_font.save(temp_ttf_file)
        temp_ttf_file.seek(0)
        pil_font = ImageFont.truetype(temp_ttf_file, FONT_SIZE)
        characters = set()
        for table in ttf_font['cmap'].tables:
            for char_code in table.cmap:
                character = chr(char_code)
                characters.add(character)
        characters = list(characters)
        print(f"First 10 characters from font (WOFF2): {characters[:10]}")

    elif font_path.lower().endswith('.ttf') or font_path.lower().endswith('.otf'):
        pil_font = ImageFont.truetype(font_path, FONT_SIZE)
        ft_font = ttFont.TTFont(font_path)
        characters = set()
        for table in ft_font['cmap'].tables:
            for char_code in table.cmap:
                character = chr(char_code)
                characters.add(character)
        characters = list(characters)
    else:
        raise ValueError("Unsupported font format. Please provide a WOFF2, TTF, or OTF file.")

    # Apply character limit if specified
    characters_to_process = characters
    if limit_chars is not None and limit_chars > 0:
        characters_to_process = characters_to_process[:limit_chars]
        print(f"Limited processing to first {limit_chars} characters")
    
    print(f"Processing {len(characters_to_process)} characters")
    
    # Phase 1: Run PaddleOCR on all characters
    print("\n--- Phase 1: PaddleOCR Processing ---")
    ocr_results = {}
    failed_characters = []
    
    for char in characters_to_process:
        recognized_char, confidence = extract_single_character_ocr(char, pil_font, confidence_threshold=0.95)
        if recognized_char is not None:
            ocr_results[char] = recognized_char
        else:
            failed_characters.append(char)
    
    print(f"OCR Results: {len(ocr_results)} successes, {len(failed_characters)} failures")
    
    # Phase 2: Apply fallback to failed characters only
    print("\n--- Phase 2: Fallback Processing for Failed Characters ---")
    fallback_results = {}
    
    if failed_characters and std_font_dict and guest_range and TRUE_FONT_PATH:
        print(f"Processing {len(failed_characters)} failed characters with image similarity")
        
        for char in failed_characters:
            try:
                # Use the same draw function as in slow.py for consistency
                char_image = draw(char, pil_font, IMAGE_SIZE)
                
                # Use image similarity fallback
                fallback_result = match_test_im_with_cache(char_image, std_font_dict, guest_range, TRUE_FONT_PATH)
                if fallback_result:
                    fallback_results[char] = fallback_result
                    print(f"FALLBACK SUCCESS: '{char}' (U+{ord(char):04X}) -> '{fallback_result}'")
                else:
                    print(f"FALLBACK FAILED: '{char}' (U+{ord(char):04X}) - no match found")
                    
            except Exception as e:
                print(f"FALLBACK ERROR: '{char}' - {str(e)}")
    elif failed_characters:
        print(f"Skipping fallback for {len(failed_characters)} characters (fallback parameters not provided)")
    
    # Phase 3: Combine results
    print("\n--- Phase 3: Combining Results ---")
    final_results = {}
    final_results.update(ocr_results)
    final_results.update(fallback_results)
    
    print(f"Final Results: {len(ocr_results)} from OCR + {len(fallback_results)} from fallback = {len(final_results)} total")
    
    return final_results
