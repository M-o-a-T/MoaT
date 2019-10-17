#include "crc.h"

u_int8_t crc8_init()
{
    return 0;
}

static const u_int8_t table8[256] = {
    0x00U,0x97U,0xB9U,0x2EU,0xE5U,0x72U,0x5CU,0xCBU,
    0x5DU,0xCAU,0xE4U,0x73U,0xB8U,0x2FU,0x01U,0x96U,
    0xBAU,0x2DU,0x03U,0x94U,0x5FU,0xC8U,0xE6U,0x71U,
    0xE7U,0x70U,0x5EU,0xC9U,0x02U,0x95U,0xBBU,0x2CU,
    0xE3U,0x74U,0x5AU,0xCDU,0x06U,0x91U,0xBFU,0x28U,
    0xBEU,0x29U,0x07U,0x90U,0x5BU,0xCCU,0xE2U,0x75U,
    0x59U,0xCEU,0xE0U,0x77U,0xBCU,0x2BU,0x05U,0x92U,
    0x04U,0x93U,0xBDU,0x2AU,0xE1U,0x76U,0x58U,0xCFU,
    0x51U,0xC6U,0xE8U,0x7FU,0xB4U,0x23U,0x0DU,0x9AU,
    0x0CU,0x9BU,0xB5U,0x22U,0xE9U,0x7EU,0x50U,0xC7U,
    0xEBU,0x7CU,0x52U,0xC5U,0x0EU,0x99U,0xB7U,0x20U,
    0xB6U,0x21U,0x0FU,0x98U,0x53U,0xC4U,0xEAU,0x7DU,
    0xB2U,0x25U,0x0BU,0x9CU,0x57U,0xC0U,0xEEU,0x79U,
    0xEFU,0x78U,0x56U,0xC1U,0x0AU,0x9DU,0xB3U,0x24U,
    0x08U,0x9FU,0xB1U,0x26U,0xEDU,0x7AU,0x54U,0xC3U,
    0x55U,0xC2U,0xECU,0x7BU,0xB0U,0x27U,0x09U,0x9EU,
    0xA2U,0x35U,0x1BU,0x8CU,0x47U,0xD0U,0xFEU,0x69U,
    0xFFU,0x68U,0x46U,0xD1U,0x1AU,0x8DU,0xA3U,0x34U,
    0x18U,0x8FU,0xA1U,0x36U,0xFDU,0x6AU,0x44U,0xD3U,
    0x45U,0xD2U,0xFCU,0x6BU,0xA0U,0x37U,0x19U,0x8EU,
    0x41U,0xD6U,0xF8U,0x6FU,0xA4U,0x33U,0x1DU,0x8AU,
    0x1CU,0x8BU,0xA5U,0x32U,0xF9U,0x6EU,0x40U,0xD7U,
    0xFBU,0x6CU,0x42U,0xD5U,0x1EU,0x89U,0xA7U,0x30U,
    0xA6U,0x31U,0x1FU,0x88U,0x43U,0xD4U,0xFAU,0x6DU,
    0xF3U,0x64U,0x4AU,0xDDU,0x16U,0x81U,0xAFU,0x38U,
    0xAEU,0x39U,0x17U,0x80U,0x4BU,0xDCU,0xF2U,0x65U,
    0x49U,0xDEU,0xF0U,0x67U,0xACU,0x3BU,0x15U,0x82U,
    0x14U,0x83U,0xADU,0x3AU,0xF1U,0x66U,0x48U,0xDFU,
    0x10U,0x87U,0xA9U,0x3EU,0xF5U,0x62U,0x4CU,0xDBU,
    0x4DU,0xDAU,0xF4U,0x63U,0xA8U,0x3FU,0x11U,0x86U,
    0xAAU,0x3DU,0x13U,0x84U,0x4FU,0xD8U,0xF6U,0x61U,
    0xF7U,0x60U,0x4EU,0xD9U,0x12U,0x85U,0xABU,0x3CU,
};

u_int8_t crc8_update(u_int8_t crc, u_int8_t byte)
{
    return table8[byte ^ crc];
}

u_int8_t crc8_update_v(u_int8_t crc, u_int16_t byte, u_int8_t n_bits)
{
    if (n_bits > 8) {
        n_bits -= 8;
        crc = table8[crc ^ (byte>>(n_bits))];
    }
    crc ^= byte << (8-n_bits);
    crc = table8[crc >> (8-n_bits)] ^ (crc<<n_bits);
    return crc;
}

u_int8_t crc8_finish(u_int8_t crc)
{
    return crc;
}

u_int8_t crc8(u_int8_t *data, u_int16_t len)
{
    u_int8_t crc = crc8_init();
    while(len--)
        crc = crc8_update(crc, *data++);
    return crc;
}


u_int16_t crc16_init()
{
    return 0;
}

static const u_int16_t table16[256] = {
/*
    0x0000U,0x1021U,0x2042U,0x3063U,0x4084U,0x50A5U,0x60C6U,0x70E7U,
    0x8108U,0x9129U,0xA14AU,0xB16BU,0xC18CU,0xD1ADU,0xE1CEU,0xF1EFU,
    0x1231U,0x0210U,0x3273U,0x2252U,0x52B5U,0x4294U,0x72F7U,0x62D6U,
    0x9339U,0x8318U,0xB37BU,0xA35AU,0xD3BDU,0xC39CU,0xF3FFU,0xE3DEU,
    0x2462U,0x3443U,0x0420U,0x1401U,0x64E6U,0x74C7U,0x44A4U,0x5485U,
    0xA56AU,0xB54BU,0x8528U,0x9509U,0xE5EEU,0xF5CFU,0xC5ACU,0xD58DU,
    0x3653U,0x2672U,0x1611U,0x0630U,0x76D7U,0x66F6U,0x5695U,0x46B4U,
    0xB75BU,0xA77AU,0x9719U,0x8738U,0xF7DFU,0xE7FEU,0xD79DU,0xC7BCU,
    0x48C4U,0x58E5U,0x6886U,0x78A7U,0x0840U,0x1861U,0x2802U,0x3823U,
    0xC9CCU,0xD9EDU,0xE98EU,0xF9AFU,0x8948U,0x9969U,0xA90AU,0xB92BU,
    0x5AF5U,0x4AD4U,0x7AB7U,0x6A96U,0x1A71U,0x0A50U,0x3A33U,0x2A12U,
    0xDBFDU,0xCBDCU,0xFBBFU,0xEB9EU,0x9B79U,0x8B58U,0xBB3BU,0xAB1AU,
    0x6CA6U,0x7C87U,0x4CE4U,0x5CC5U,0x2C22U,0x3C03U,0x0C60U,0x1C41U,
    0xEDAEU,0xFD8FU,0xCDECU,0xDDCDU,0xAD2AU,0xBD0BU,0x8D68U,0x9D49U,
    0x7E97U,0x6EB6U,0x5ED5U,0x4EF4U,0x3E13U,0x2E32U,0x1E51U,0x0E70U,
    0xFF9FU,0xEFBEU,0xDFDDU,0xCFFCU,0xBF1BU,0xAF3AU,0x9F59U,0x8F78U,
    0x9188U,0x81A9U,0xB1CAU,0xA1EBU,0xD10CU,0xC12DU,0xF14EU,0xE16FU,
    0x1080U,0x00A1U,0x30C2U,0x20E3U,0x5004U,0x4025U,0x7046U,0x6067U,
    0x83B9U,0x9398U,0xA3FBU,0xB3DAU,0xC33DU,0xD31CU,0xE37FU,0xF35EU,
    0x02B1U,0x1290U,0x22F3U,0x32D2U,0x4235U,0x5214U,0x6277U,0x7256U,
    0xB5EAU,0xA5CBU,0x95A8U,0x8589U,0xF56EU,0xE54FU,0xD52CU,0xC50DU,
    0x34E2U,0x24C3U,0x14A0U,0x0481U,0x7466U,0x6447U,0x5424U,0x4405U,
    0xA7DBU,0xB7FAU,0x8799U,0x97B8U,0xE75FU,0xF77EU,0xC71DU,0xD73CU,
    0x26D3U,0x36F2U,0x0691U,0x16B0U,0x6657U,0x7676U,0x4615U,0x5634U,
    0xD94CU,0xC96DU,0xF90EU,0xE92FU,0x99C8U,0x89E9U,0xB98AU,0xA9ABU,
    0x5844U,0x4865U,0x7806U,0x6827U,0x18C0U,0x08E1U,0x3882U,0x28A3U,
    0xCB7DU,0xDB5CU,0xEB3FU,0xFB1EU,0x8BF9U,0x9BD8U,0xABBBU,0xBB9AU,
    0x4A75U,0x5A54U,0x6A37U,0x7A16U,0x0AF1U,0x1AD0U,0x2AB3U,0x3A92U,
    0xFD2EU,0xED0FU,0xDD6CU,0xCD4DU,0xBDAAU,0xAD8BU,0x9DE8U,0x8DC9U,
    0x7C26U,0x6C07U,0x5C64U,0x4C45U,0x3CA2U,0x2C83U,0x1CE0U,0x0CC1U,
    0xEF1FU,0xFF3EU,0xCF5DU,0xDF7CU,0xAF9BU,0xBFBAU,0x8FD9U,0x9FF8U,
    0x6E17U,0x7E36U,0x4E55U,0x5E74U,0x2E93U,0x3EB2U,0x0ED1U,0x1EF0U,
*/
    0x0000U,0xBAADU,0xCFF7U,0x755AU,0x2543U,0x9FEEU,0xEAB4U,0x5019U,
    0x4A86U,0xF02BU,0x8571U,0x3FDCU,0x6FC5U,0xD568U,0xA032U,0x1A9FU,
    0x950CU,0x2FA1U,0x5AFBU,0xE056U,0xB04FU,0x0AE2U,0x7FB8U,0xC515U,
    0xDF8AU,0x6527U,0x107DU,0xAAD0U,0xFAC9U,0x4064U,0x353EU,0x8F93U,
    0x90B5U,0x2A18U,0x5F42U,0xE5EFU,0xB5F6U,0x0F5BU,0x7A01U,0xC0ACU,
    0xDA33U,0x609EU,0x15C4U,0xAF69U,0xFF70U,0x45DDU,0x3087U,0x8A2AU,
    0x05B9U,0xBF14U,0xCA4EU,0x70E3U,0x20FAU,0x9A57U,0xEF0DU,0x55A0U,
    0x4F3FU,0xF592U,0x80C8U,0x3A65U,0x6A7CU,0xD0D1U,0xA58BU,0x1F26U,
    0x9BC7U,0x216AU,0x5430U,0xEE9DU,0xBE84U,0x0429U,0x7173U,0xCBDEU,
    0xD141U,0x6BECU,0x1EB6U,0xA41BU,0xF402U,0x4EAFU,0x3BF5U,0x8158U,
    0x0ECBU,0xB466U,0xC13CU,0x7B91U,0x2B88U,0x9125U,0xE47FU,0x5ED2U,
    0x444DU,0xFEE0U,0x8BBAU,0x3117U,0x610EU,0xDBA3U,0xAEF9U,0x1454U,
    0x0B72U,0xB1DFU,0xC485U,0x7E28U,0x2E31U,0x949CU,0xE1C6U,0x5B6BU,
    0x41F4U,0xFB59U,0x8E03U,0x34AEU,0x64B7U,0xDE1AU,0xAB40U,0x11EDU,
    0x9E7EU,0x24D3U,0x5189U,0xEB24U,0xBB3DU,0x0190U,0x74CAU,0xCE67U,
    0xD4F8U,0x6E55U,0x1B0FU,0xA1A2U,0xF1BBU,0x4B16U,0x3E4CU,0x84E1U,
    0x8D23U,0x378EU,0x42D4U,0xF879U,0xA860U,0x12CDU,0x6797U,0xDD3AU,
    0xC7A5U,0x7D08U,0x0852U,0xB2FFU,0xE2E6U,0x584BU,0x2D11U,0x97BCU,
    0x182FU,0xA282U,0xD7D8U,0x6D75U,0x3D6CU,0x87C1U,0xF29BU,0x4836U,
    0x52A9U,0xE804U,0x9D5EU,0x27F3U,0x77EAU,0xCD47U,0xB81DU,0x02B0U,
    0x1D96U,0xA73BU,0xD261U,0x68CCU,0x38D5U,0x8278U,0xF722U,0x4D8FU,
    0x5710U,0xEDBDU,0x98E7U,0x224AU,0x7253U,0xC8FEU,0xBDA4U,0x0709U,
    0x889AU,0x3237U,0x476DU,0xFDC0U,0xADD9U,0x1774U,0x622EU,0xD883U,
    0xC21CU,0x78B1U,0x0DEBU,0xB746U,0xE75FU,0x5DF2U,0x28A8U,0x9205U,
    0x16E4U,0xAC49U,0xD913U,0x63BEU,0x33A7U,0x890AU,0xFC50U,0x46FDU,
    0x5C62U,0xE6CFU,0x9395U,0x2938U,0x7921U,0xC38CU,0xB6D6U,0x0C7BU,
    0x83E8U,0x3945U,0x4C1FU,0xF6B2U,0xA6ABU,0x1C06U,0x695CU,0xD3F1U,
    0xC96EU,0x73C3U,0x0699U,0xBC34U,0xEC2DU,0x5680U,0x23DAU,0x9977U,
    0x8651U,0x3CFCU,0x49A6U,0xF30BU,0xA312U,0x19BFU,0x6CE5U,0xD648U,
    0xCCD7U,0x767AU,0x0320U,0xB98DU,0xE994U,0x5339U,0x2663U,0x9CCEU,
    0x135DU,0xA9F0U,0xDCAAU,0x6607U,0x361EU,0x8CB3U,0xF9E9U,0x4344U,
    0x59DBU,0xE376U,0x962CU,0x2C81U,0x7C98U,0xC635U,0xB36FU,0x09C2U,
};

u_int16_t crc16_update(u_int16_t crc, u_int8_t byte)
{
    
    crc = table16[byte ^ (crc>>8)] ^ (crc << 8);
    return crc;
}

u_int16_t crc16_update_v(u_int16_t crc, u_int16_t byte, u_int8_t n_bits)
{
    crc ^= byte<<(16-n_bits);
    if (n_bits > 8) {
        crc = table16[crc>>8] ^ (crc << 8);
        n_bits -= 8;
    }
    crc = table16[crc >> (16-n_bits)] ^ (crc<<n_bits);
    return crc;
}


u_int16_t crc16_finish(u_int16_t crc)
{
    return crc;
}

u_int16_t crc16(u_int8_t *data, u_int16_t len)
{
    u_int16_t crc = crc16_init();
    while(len--)
        crc = crc16_update(crc, *data++);
    return crc;
}

