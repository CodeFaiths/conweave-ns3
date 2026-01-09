/* -*- Mode:C++; c-file-style:"gnu"; indent-tabs-mode:nil; -*- */
/*
 * Copyright (c) 2024
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License version 2 as
 * published by the Free Software Foundation;
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
 *
 * Author: Credit-based PFC Enhancement Module
 */

#include <stdint.h>
#include <iostream>
#include "credit-feedback-header.h"
#include "ns3/buffer.h"
#include "ns3/log.h"

NS_LOG_COMPONENT_DEFINE("CreditFeedbackHeader");

namespace ns3 {

NS_OBJECT_ENSURE_REGISTERED(CreditFeedbackHeader);

CreditFeedbackHeader::CreditFeedbackHeader()
    : m_queueLen(0), m_gradient(0), m_creditValue(0), m_portIndex(0) {
}

CreditFeedbackHeader::CreditFeedbackHeader(uint32_t queueLen, int16_t gradient, 
                                           uint16_t creditValue, uint8_t portIndex)
    : m_queueLen(queueLen), m_gradient(gradient), 
      m_creditValue(creditValue), m_portIndex(portIndex) {
}

CreditFeedbackHeader::~CreditFeedbackHeader() {
}

void CreditFeedbackHeader::SetQueueLen(uint32_t queueLen) {
    m_queueLen = queueLen;
}

uint32_t CreditFeedbackHeader::GetQueueLen() const {
    return m_queueLen;
}

void CreditFeedbackHeader::SetGradient(int16_t gradient) {
    m_gradient = gradient;
}

int16_t CreditFeedbackHeader::GetGradient() const {
    return m_gradient;
}

void CreditFeedbackHeader::SetCreditValue(uint16_t creditValue) {
    m_creditValue = creditValue;
}

uint16_t CreditFeedbackHeader::GetCreditValue() const {
    return m_creditValue;
}

void CreditFeedbackHeader::SetPortIndex(uint8_t portIndex) {
    m_portIndex = portIndex;
}

uint8_t CreditFeedbackHeader::GetPortIndex() const {
    return m_portIndex;
}

TypeId CreditFeedbackHeader::GetTypeId(void) {
    static TypeId tid = TypeId("ns3::CreditFeedbackHeader")
        .SetParent<Header>()
        .AddConstructor<CreditFeedbackHeader>();
    return tid;
}

TypeId CreditFeedbackHeader::GetInstanceTypeId(void) const {
    return GetTypeId();
}

void CreditFeedbackHeader::Print(std::ostream &os) const {
    os << "queueLen=" << m_queueLen 
       << ", gradient=" << m_gradient
       << ", creditValue=" << m_creditValue 
       << ", portIndex=" << (int)m_portIndex;
}

uint32_t CreditFeedbackHeader::GetSerializedSize(void) const {
    // 4 + 2 + 2 + 1 = 9 bytes
    return 9;
}

void CreditFeedbackHeader::Serialize(Buffer::Iterator start) const {
    start.WriteU32(m_queueLen);
    start.WriteU16((uint16_t)m_gradient);
    start.WriteU16(m_creditValue);
    start.WriteU8(m_portIndex);
}

uint32_t CreditFeedbackHeader::Deserialize(Buffer::Iterator start) {
    m_queueLen = start.ReadU32();
    m_gradient = (int16_t)start.ReadU16();
    m_creditValue = start.ReadU16();
    m_portIndex = start.ReadU8();
    return GetSerializedSize();
}

} // namespace ns3
